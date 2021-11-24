from __future__ import annotations

import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from typing import Any, Dict, FrozenSet

from frozendict import frozendict
from loguru import logger
from python_on_whales import DockerClient as WhaleClient
from pytimeparse import timeparse

from .errors import SwarmException, SwarmWarning
from .nodes import ManagerNode, SwarmNode, WorkerNode
from .workload import WorkloadResult, WorkloadSpecification
from ..misc import RepeatingTimer
from ..network import WorkloadNetwork


class DockerSwarm(AbstractContextManager):
    """
    Implements an simple interface to a Docker swarm, built on top of hosts
    from a workload network. Can be used as a context manager, in which case the
    created instance is bound to the 'as' variable.

    Note that the Swarm is built up such that data traverses the workload
    network but management traffic stays on the management network.
    """

    _daemon_port = 2375
    _unhealthy_task_states = ('failed', 'rejected', 'orphaned')

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

                def _add_node(args: Dict) -> None:
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

        except:
            logger.error('Error when constructing Docker Swarm, gracefully '
                         'tearing down.')
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
    def managers(self) -> FrozenSet[ManagerNode]:
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
        return frozenset(self._managers.values())

    @property
    def workers(self) -> FrozenSet[WorkerNode]:
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
        return frozenset(self._workers.keys())

    def deploy_workload(self,
                        specification: WorkloadSpecification,
                        health_check_poll_interval: float = 10.0) \
            -> WorkloadResult:
        """
        Runs a workload, as described by a WorkloadDefinition object, on this
        Swarm and waits for it to finish (or fail).

        Parameters
        ----------
        specification
            The workload spec to deploy.
        health_check_poll_interval
            How often to check the health of the deployed services, in seconds.

        Returns
        -------
        WorkloadResult
            An Enum indicating the exit status of the workload.
        """
        logger.info(f'Deploying workload {specification.name}.')

        with specification.temp_compose_file() as compose_file:
            logger.debug(f'Using temporary docker-compose v3 at '
                         f'{compose_file}.')

            # we use python-on-whales to deploy the service stack,
            # since docker-py is too low-level.

            # grab an arbitrary manager and point a client to it
            mgr_id, mgr_node = next(iter(self._managers.items()))
            host_addr = f'{mgr_node.host.management_ip.ip}:' \
                        f'{mgr_node.daemon_port}'

            stack = WhaleClient(host=host_addr).stack.deploy(
                name=specification.name,
                compose_files=[compose_file],
                orchestrator='swarm',
            )

            # TODO: environment files
            # TODO: variables in compose? really useful!
            # TODO: logging. could be handled here instead of in fluentbit

            # convert the python-on-whales service objects into pure
            # Docker-Py Service objects for more efficient health checks

            with mgr_node.client_context() as client:
                services = [client.services.get(s.id) for s in stack.services()]

            # start health checks and countdown to max duration

            # thread functions
            # ----------------
            timed_out = threading.Event()
            unhealthy_event = threading.Event()
            finished_event = threading.Event()
            status_cond = threading.Condition()

            def _wkld_timeout():
                logger.warning(f'Workload {specification.name} timed out!')
                with status_cond:
                    timed_out.set()
                    status_cond.notify_all()

            def _health_check() -> bool:
                complete = True
                for serv in services:
                    # update service status from the client,
                    # then iterate over tasks and check if they are healthy.
                    serv.reload()
                    serv_name = serv.attrs['Spec']['Name']
                    for task in serv.tasks():
                        task_id = task['ID']
                        task_state = task['Status']['State'].lower()
                        if task_state in self._unhealthy_task_states:
                            logger.critical(
                                f'Unhealthy task {task_id} (state: '
                                f'{task_state} in service {serv_name}; '
                                f'aborting workload {specification.name}!'
                            )

                            with status_cond:
                                unhealthy_event.set()
                                status_cond.notify_all()
                                return False
                        elif task_state == 'complete':
                            logger.warning(
                                f'Task {task_id} in service {serv_name} '
                                f'has finished.'
                            )
                            complete = (complete and True)
                        else:
                            complete = False

                logger.info(f'Workload {specification.name} has passed health '
                            f'check.')
                if complete:
                    logger.warning(
                        f'All tasks in workload {specification.name} '
                        f'have finished.')
                    with status_cond:
                        finished_event.set()
                        status_cond.notify_all()
                        return False

                return True

            # ----------------

            max_duration = timeparse.timeparse(specification.max_duration,
                                               granularity='seconds')
            timeout_timer = threading.Timer(interval=max_duration,
                                            function=_wkld_timeout)
            timeout_timer.start()

            health_check_timer = RepeatingTimer(
                interval=health_check_poll_interval,
                function=_health_check
            )
            health_check_timer.start()

            # block and wait for workload to either finish, fail, or time-out.
            result = WorkloadResult.ERROR
            try:
                with status_cond:
                    while True:
                        if timed_out.is_set():
                            # TODO: special handling for time-out?
                            result = WorkloadResult.TIMEOUT
                        elif unhealthy_event.is_set():
                            # TODO: special handling for unhealthy workload?
                            result = WorkloadResult.ERROR
                        elif finished_event.is_set():
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

                logger.warning('Tearing down Docker Swarm service stack for '
                               f'workload {specification.name}.')
                stack.remove()

            return result
