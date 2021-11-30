from __future__ import annotations

import threading
import warnings
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from typing import Any, Collection, Dict, FrozenSet, Optional

from docker.models.services import Service
from frozendict import frozendict
from loguru import logger
from python_on_whales import DockerClient as WhaleClient, DockerException
from pytimeparse import timeparse

from .errors import SwarmException, SwarmWarning
from .nodes import ManagerNode, SwarmNode, WorkerNode
from .workload import WorkloadResult, WorkloadSpecification
from ..misc import RepeatingTimer, seconds2hms
from ..network import WorkloadNetwork


# TODO: daemon port should be handled in hosts?

class ServiceHealthCheckThread(RepeatingTimer):
    # checking for x in set is O(1)
    _unhealthy_task_states = {'failed', 'rejected', 'orphaned'}

    def __init__(self,
                 shared_condition: threading.Condition,
                 services: Collection[Service],
                 check_interval: float,
                 complete_thresh: int = 3,
                 max_failed_health_checks: int = 3):
        super(ServiceHealthCheckThread, self).__init__(
            interval=check_interval,
            function=self.health_check
        )
        self._shared_cond = shared_condition
        self._unhealthy = threading.Event()
        self._finished = threading.Event()
        self._services = services
        self._complete_thresh = complete_thresh
        self._max_failed_checks = max_failed_health_checks
        self._fail_count = 0
        self._complete_count = 0

    def is_healthy(self) -> bool:
        return not self._unhealthy.is_set()

    def is_finished(self) -> bool:
        return self._finished.is_set()

    def _is_task_healthy(self, task: Dict[str, Any]) -> bool:
        state = task.get('Status', {}).get('State', None)
        task_id = task.get('ID', None)
        logger.debug(f'Task {task_id} state: {state}')
        return (state is not None) and \
               (state not in self._unhealthy_task_states)

    def health_check(self) -> bool:
        try:
            complete = True
            unhealthy = False
            for serv in self._services:
                serv.reload()
                # we only care about tasks that *should* be running
                tasks = serv.tasks(filters={'desired-state': 'running'})
                total_tasks = len(tasks)

                if total_tasks == 0:
                    complete = (complete and True)
                    logger.info(f'Service {serv.name} currently has no tasks.')
                    continue

                complete = False
                healthy_tasks = sum([self._is_task_healthy(task)
                                     for task in tasks])

                if healthy_tasks < total_tasks:
                    logger.warning(f'Service {serv.name}: '
                                   f'{total_tasks - healthy_tasks} out of'
                                   f'{total_tasks} tasks are unhealthy.')
                    unhealthy = True
                else:
                    logger.info(f'Service {serv.name}: All tasks are healthy.')

            if unhealthy:
                self._fail_count += 1
                logger.warning(f'Unhealthy services. Check '
                               f'{self._fail_count}/'
                               f'{self._max_failed_checks} '
                               f'failed.')
                if self._fail_count >= self._max_failed_checks:
                    logger.error('Maximum number of health checks failed, '
                                 'aborting workload.')
                    with self._shared_cond:
                        self._unhealthy.set()
                        self._shared_cond.notify_all()
                        return False
                return True
            elif complete:
                self._complete_count += 1
                logger.info(f'All services complete. '
                            f'{self._complete_count}/{self._complete_thresh} '
                            f'checks passed before workload shutdown.')
                if self._complete_count >= self._complete_thresh:
                    logger.warning('All services have finished and exited '
                                   'cleanly; shutting down workload.')
                    with self._shared_cond:
                        self._finished.set()
                        self._shared_cond.notify_all()
                        return False
                return True

            self._complete_count = 0
            self._fail_count = 0
            return True

        except Exception as e:
            # any failure should cause this thread to shut down and set the flag
            # to unhealthy!
            logger.exception('Exception in health check thread.', e)
            with self._shared_cond:
                self._unhealthy.set()
                self._shared_cond.notify_all()
                return False


class DockerSwarm(AbstractContextManager):
    """
    Implements an simple interface to a Docker swarm, built on top of hosts
    from a workload network. Can be used as a context manager, in which case the
    created instance is bound to the 'as' variable.

    Note that the Swarm is built up such that data traverses the workload
    network but management traffic stays on the management network.
    """

    _daemon_port = 2375

    def __init__(self,
                 network: WorkloadNetwork,
                 managers: Dict[str, Dict[str, Any]],
                 workers: Dict[str, Dict[str, Any]]):
        """
        Parameters
        ----------
        network
            Workload network to build this Swarm on top off.
        managers
            Dictionary of hostnames to node labels for manager nodes. Needs
            to contain at least one key-value pair.
        workers
            Dictionary of hostnames to node labels for manager nodes.

        Raises
        ------
        SwarmException
            If the manager dictionary contains no elements.
        """

        logger.info('Setting up Docker Swarm.')

        # sanity checks

        if len(managers) < 1:
            raise SwarmException('At least one manager node is needed to '
                                 'bring up Docker Swarm!')

        for host in managers:
            try:
                workers.pop(host)
                warnings.warn(f'Ambiguous Swarm definition: host {host} '
                              f'specified both as a manager and a worker. '
                              f'Dropping worker definition for sanity.',
                              SwarmWarning)
            except KeyError:
                pass

        logger.info(f'Docker Swarm managers: {list(managers.keys())}')
        logger.info(f'Docker Swarm workers: {list(workers.keys())}')

        # build the swarm, managers first
        manager_nodes = dict()
        worker_nodes = dict()
        try:
            try:
                host_id, labels = managers.popitem()
            except KeyError as e:
                raise SwarmException('At least one manager is required for '
                                     'Docker Swarm initialization!') from e
            first_manager_node = ManagerNode.init_swarm(
                name=host_id,
                host=network[host_id],
                labels=labels,
                daemon_port=self._daemon_port
            )
            manager_nodes[host_id] = first_manager_node

            # rest of nodes are added in parallel
            with ThreadPoolExecutor() as tpool:
                # use thread pool instead of process pool, as we only really
                # need I/O concurrency (Docker client comms) and threads are
                # much more lightweight than processes
                exc_lock = threading.RLock()
                caught_exceptions = deque()

                def _add_node(args: Dict) -> None:
                    try:
                        if args['manager']:
                            node = first_manager_node.attach_manager(
                                name=args['id'],
                                host=args['host'],
                                labels=args['labels'],
                                daemon_port=self._daemon_port
                            )
                            manager_nodes[args['id']] = node
                        else:
                            node = first_manager_node.attach_worker(
                                name=args['id'],
                                host=args['host'],
                                labels=args['labels'],
                                daemon_port=self._daemon_port
                            )
                            worker_nodes[args['id']] = node
                    except Exception as e:
                        with exc_lock:
                            caught_exceptions.append(e)

                # NOTE: ThreadPoolExecutor.map does not block, as opposed to
                # ProcessPool.map; it immediately returns an iterator.
                # Here we force it to block by immediately exiting the with
                # block, which causes the pool to wait for all threads and
                # then shut down.
                tpool.map(_add_node,
                          [
                              {
                                  'manager': True,
                                  'id'     : host_id,
                                  'host'   : network[host_id],
                                  'labels' : labels,
                              }
                              for host_id, labels in managers.items()
                          ] + [
                              {
                                  'manager': False,
                                  'id'     : host_id,
                                  'host'   : network[host_id],
                                  'labels' : labels,
                              }
                              for host_id, labels in workers.items()
                          ])

            if len(caught_exceptions) > 0:
                raise SwarmException('Could not attach all nodes to Swarm.') \
                    from caught_exceptions.pop()

        except Exception as e:
            logger.error('Caught exception when constructing Docker '
                         'Swarm, gracefully tearing down.')
            logger.exception('Exception', e)
            # in case of ANYTHING going wrong, we need to tear down the swarm
            # on nodes on which it has already been initialized

            for nodes in (worker_nodes, manager_nodes):
                for node_id, node in nodes.items():
                    node.leave_swarm(force=True)

            raise

        self._managers = frozendict(manager_nodes)
        self._workers = frozendict(worker_nodes)
        self._torn_down = False
        self._n_nodes = len(self._managers) + len(self._workers)

    def _check(self) -> None:
        if self._torn_down:
            raise SwarmException('Swarm has been torn down.')

    @property
    def num_nodes(self) -> int:
        """
        Returns
        -------
        int
            The number of nodes in this Swarm.
        """
        return self._n_nodes

    def __len__(self) -> int:
        return self.num_nodes

    def tear_down(self) -> None:
        """
        Convenience method to fully tear down this swarm.
        This object will be in an invalid state afterwards and should not be
        used any more.
        """

        if self._torn_down:
            logger.warning('Trying to tear down already torn-down Swarm; '
                           'doing nothing.')
            return

        logger.warning('Tearing down Swarm!')
        with ThreadPoolExecutor() as tpool:
            def leave_swarm(node: SwarmNode) -> None:
                node.leave_swarm(force=True)

            # NOTE: see comment about .map blocking further up.
            tpool.map(leave_swarm,
                      list(self._managers.values()) +
                      list(self._workers.values()))

        logger.warning('Swarm has been torn down.')

    def __enter__(self) -> DockerSwarm:
        self._check()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # on exit, we tear down this swarm
        self.tear_down()
        return super(DockerSwarm, self).__exit__(exc_type, exc_val, exc_tb)

    @property
    def managers(self) -> frozendict[str, ManagerNode]:
        """
        Returns
        -------
        FrozenSet
            A view into the Manager nodes of this Swarm.

        Raises
        ------
        SwarmException
            If Swarm has been torn down.
        """
        self._check()
        return frozendict(self._managers)

    @property
    def workers(self) -> frozendict[str, WorkerNode]:
        """
        Returns
        -------
        FrozenSet
            A view into the Worker nodes of this Swarm.

        Raises
        ------
        SwarmException
            If Swarm has been torn down.
        """
        self._check()
        return frozendict(self._workers)

    def deploy_workload(self,
                        specification: WorkloadSpecification,
                        attach_volume: Optional[str] = None,
                        health_check_poll_interval: float = 10.0,
                        complete_threshold: int = 3,
                        max_failed_health_checks: int = 3) \
            -> WorkloadResult:
        """
        Runs a workload, as described by a WorkloadDefinition object, on this
        Swarm and waits for it to finish (or fail).

        Parameters
        ----------
        specification
            The workload spec to deploy.
        attach_volume
            Specifies the name of an external Docker volume to be appended to
            the stack volumes. If None, nothing is appended.
        health_check_poll_interval
            How often to check the health of the deployed services, in seconds.
        complete_threshold
            How many health checks need to be passed with all services
            completed before the workload shuts down.
        max_failed_health_checks
            How many failed health checks to allow before aborting the workload.

        Returns
        -------
        WorkloadResult
            An Enum indicating the exit status of the workload.
        """
        logger.info(f'Deploying workload {specification.name}:\n'
                    f'{specification}')

        # TODO: figure out a way to pull images before deploying

        # calculate  time log formats before launching to not
        # interfere with actual duration
        max_duration = timeparse.timeparse(specification.max_duration,
                                           granularity='seconds')
        max_dur_hms = seconds2hms(max_duration)
        health_ival_hms = seconds2hms(health_check_poll_interval)

        log_max_fails = max_failed_health_checks \
            if max_failed_health_checks > 0 else '∞'

        logger.info(f'Max workload runtime: {max_dur_hms}')
        logger.info(f'Health check interval: {health_ival_hms}; maximum '
                    f'allowed failed health checks: {log_max_fails}.')

        with specification.temp_compose_file(attach_volume) as compose_file:
            logger.debug(f'Using temporary docker-compose v3 at '
                         f'{compose_file}.')

            # we use python-on-whales to deploy the service stack,
            # since docker-py is too low-level.

            # grab an arbitrary manager and point a client to it
            mgr_id, mgr_node = next(iter(self._managers.items()))
            host_addr = f'{mgr_node.host.management_ip.ip}:' \
                        f'{mgr_node.daemon_port}'

            try:
                stack = WhaleClient(host=host_addr).stack.deploy(
                    name=specification.name,
                    compose_files=[compose_file],
                    orchestrator='swarm',
                )
            except DockerException as e:
                logger.exception('Caught exception when deploying workload '
                                 'service stack to Swarm.', e)
                raise e

            # TODO: environment files
            # TODO: variables in compose? really useful!
            # TODO: logging. could be handled here instead of in fluentbit

            # convert the python-on-whales service objects into pure
            # Docker-Py Service objects for more efficient health checks

            with mgr_node.client_context() as client:
                services = [client.services.get(s.id)
                            for s in stack.services()]

            logger.warning(f'Workload {specification.name} '
                           f'({len(services)} services) has been deployed!')

            # start health checks and countdown to max duration
            # thread functions
            # ----------------
            timed_out = threading.Event()
            status_cond = threading.Condition()

            def _wkld_timeout():
                logger.warning(f'Workload {specification.name} timed out!')
                with status_cond:
                    timed_out.set()
                    status_cond.notify_all()

            # ----------------

            timeout_timer = threading.Timer(interval=max_duration,
                                            function=_wkld_timeout)
            timeout_timer.start()

            health_check_timer = ServiceHealthCheckThread(
                shared_condition=status_cond,
                services=services,
                check_interval=health_check_poll_interval,
                complete_thresh=complete_threshold,
                max_failed_health_checks=max_failed_health_checks
            )
            health_check_timer.start()

            # block and wait for workload to either finish, fail,
            # or time-out.
            result = WorkloadResult.ERROR
            try:
                with status_cond:
                    # TODO: handle ctrl c
                    # TODO: extend to client-server architecture?
                    while True:
                        if timed_out.is_set():
                            # TODO: special handling for time-out?
                            result = WorkloadResult.TIMEOUT
                        elif not health_check_timer.is_healthy():
                            # TODO: special handling for unhealthy workload?
                            result = WorkloadResult.ERROR
                        elif health_check_timer.is_finished():
                            # TODO: special handling for clean shutdown?
                            result = WorkloadResult.FINISHED
                        else:
                            status_cond.wait()
                            continue
                        break
            finally:
                # whatever happens, at this point we stop the threads and
                # tear down the service stack
                timeout_timer.cancel()
                health_check_timer.cancel()
                timeout_timer.join()
                health_check_timer.join()

                logger.warning('Tearing down Docker Swarm service '
                               'stack for workload {specification.name}.')
                stack.remove()

            return result
