from __future__ import annotations

import itertools
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from typing import (
    Any,
    Collection,
    Dict,
    FrozenSet,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
)

from docker.models.services import Service
from loguru import logger
from python_on_whales import DockerClient as WhaleClient, DockerException
from pytimeparse import timeparse

from .errors import SwarmException
from .nodes import ManagerNode, SwarmNode, WorkerNode
from .workload import WorkloadResult, WorkloadSpecification
from ..hosts import AinurHost
from ..misc import RepeatingTimer, seconds2hms


# TODO: daemon port should be handled in hosts?


class ServiceHealthCheckThread(RepeatingTimer):
    # checking for x in set is O(1)
    _unhealthy_task_states = {"failed", "rejected", "orphaned"}

    def __init__(
        self,
        shared_condition: threading.Condition,
        services: Collection[Service],
        check_interval: float,
        complete_thresh: int = 3,
        max_failed_health_checks: int = 3,
        ignored_services: Collection[Service] = (),
    ):
        super(ServiceHealthCheckThread, self).__init__(
            interval=check_interval, function=self.health_check
        )
        self._shared_cond = shared_condition
        self._unhealthy = threading.Event()
        self._finished = threading.Event()
        self._services = {}

        for s in services:
            self._services[s] = False
        for s in ignored_services:
            self._services[s] = True

        self._complete_thresh = complete_thresh
        self._max_failed_checks = max_failed_health_checks
        self._fail_count = 0
        self._complete_count = 0

    def is_healthy(self) -> bool:
        return not self._unhealthy.is_set()

    def is_finished(self) -> bool:
        return self._finished.is_set()

    def _is_task_healthy(self, task: Dict[str, Any]) -> bool:
        state = task.get("Status", {}).get("State", None)
        task_id = task.get("ID", None)
        logger.debug(f"Task {task_id} state: {state}")
        return (state is not None) and (state not in self._unhealthy_task_states)

    def health_check(self) -> bool:
        try:
            complete = True
            unhealthy = False
            for serv, ignored in self._services.items():
                serv.reload()
                # we only care about tasks that *should* be running
                tasks = serv.tasks(filters={"desired-state": "running"})
                total_tasks = len(tasks)

                if ignored:
                    logger.warning(f"Service {serv.name}: health checks ignored.")

                if total_tasks == 0:
                    complete = (complete and True) if not ignored else complete
                    logger.info(f"Service {serv.name} currently has no tasks.")
                    continue

                complete = False if not ignored else complete
                healthy_tasks = sum([self._is_task_healthy(task) for task in tasks])

                if healthy_tasks < total_tasks:
                    logger.warning(
                        f"Service {serv.name}: "
                        f"{total_tasks - healthy_tasks} out of"
                        f"{total_tasks} tasks are unhealthy."
                    )
                    unhealthy = True if not ignored else unhealthy
                else:
                    logger.info(f"Service {serv.name}: All tasks are healthy.")

            if unhealthy:
                self._fail_count += 1
                logger.warning(
                    f"Unhealthy services. Check "
                    f"{self._fail_count}/"
                    f"{self._max_failed_checks} "
                    f"failed."
                )
                if self._fail_count >= self._max_failed_checks:
                    logger.error(
                        "Maximum number of health checks failed, " "aborting workload."
                    )
                    with self._shared_cond:
                        self._unhealthy.set()
                        self._shared_cond.notify_all()
                        return False
                return True
            elif complete:
                self._complete_count += 1
                logger.info(
                    f"All services complete. "
                    f"{self._complete_count}/{self._complete_thresh} "
                    f"checks passed before workload shutdown."
                )
                if self._complete_count >= self._complete_thresh:
                    logger.warning(
                        "All services have finished and exited "
                        "cleanly; shutting down workload."
                    )
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
            logger.exception("Exception in health check thread.", e)
            with self._shared_cond:
                self._unhealthy.set()
                self._shared_cond.notify_all()
                return False


class DockerSwarm(AbstractContextManager):
    """
    Implements a simple interface to a Docker swarm, built on top of hosts
    from a workload network. Can be used as a context manager, in which case the
    created instance is bound to the 'as' variable.

    Note that the Swarm is built up such that data traverses the workload
    network but management traffic stays on the management network.
    """

    _daemon_port = 2375

    def __init__(self):
        self._manager_nodes: Set[ManagerNode] = set()
        self._worker_nodes: Set[WorkerNode] = set()

    def deploy_managers(
        self,
        hosts: Mapping[AinurHost, Dict[str, Any]],
        **default_labels: Any,
    ) -> DockerSwarm:
        """
        Configures Manager nodes on the Swarm.

        Parameters
        ----------
        hosts
            A mapping from AinurHosts to dictionaries of labels.
        default_labels
            All other keyword arguments are treated as default values for
            labels.

        Returns
        -------
        self
            For chaining.
        """

        hosts = dict(hosts)
        while len(hosts) > 0:
            try:
                mgr_node = self._manager_nodes.pop()
                self._manager_nodes.add(mgr_node)

                logger.info(f"Deploying hosts {hosts.keys()} as Swarm " f"managers.")

                with ThreadPoolExecutor() as tpool:
                    # use thread pool instead of process pool, as we only really
                    # need I/O concurrency (Docker client comms) and threads are
                    # much more lightweight than processes
                    exc_lock = threading.RLock()
                    caught_exceptions = deque()

                    def _add_manager(h_l: Tuple[AinurHost, Dict]) -> None:
                        host, host_labels = h_l
                        labels = dict(default_labels)
                        labels.update(host_labels)
                        try:
                            node = mgr_node.attach_manager(
                                host=host, labels=labels, daemon_port=self._daemon_port
                            )
                            self._manager_nodes.add(node)
                        except Exception as e:
                            with exc_lock:
                                caught_exceptions.append(e)

                    # NOTE: ThreadPoolExecutor.map does not block, as opposed to
                    # ProcessPool.map; it immediately returns an iterator.
                    # Here we force it to block by immediately exiting the with
                    # block, which causes the pool to wait for all threads and
                    # then shut down.
                    tpool.map(_add_manager, hosts.items())

                if len(caught_exceptions) > 0:
                    raise SwarmException(
                        f"Could not attach all nodes in " f"{hosts.keys()} to Swarm."
                    ) from caught_exceptions.pop()

                hosts.clear()
                return self
            except KeyError:
                # if no existing managers, first create the swarm
                host, host_labels = hosts.popitem()
                labels = dict(default_labels)
                labels.update(host_labels)
                first_manager_node = ManagerNode.init_swarm(
                    host=host, labels=labels, daemon_port=self._daemon_port
                )
                self._manager_nodes.add(first_manager_node)
                continue
        return self

    def pull_image(self, image: str, tag: str = "latest"):
        """
        Pulls a container image on all the Swarm nodes.

        Parameters
        ----------
        image
            Image ID/repository
        tag
            Image tag.
        """

        # TODO: put this pattern in a separate function/class
        with ThreadPoolExecutor() as tpool:
            exc_lock = threading.RLock()
            caught_exceptions = deque()

            def _pull(node_img_tag: Tuple[SwarmNode, str, str]) -> None:
                node, img, tag = node_img_tag
                try:
                    node.pull_image(img, tag)
                except Exception as e:
                    with exc_lock:
                        caught_exceptions.append(e)

            tpool.map(
                _pull,
                zip(
                    self._manager_nodes, itertools.repeat(image), itertools.repeat(tag)
                ),
            )
            tpool.map(
                _pull,
                zip(self._worker_nodes, itertools.repeat(image), itertools.repeat(tag)),
            )

        if len(caught_exceptions) > 0:
            raise SwarmException(
                f"Could not pull image {image}:{tag} on all " f"nodes of the Swarm!"
            ) from caught_exceptions.pop()

    def deploy_workers(
        self,
        hosts: Mapping[AinurHost, Dict[str, Any]],
        **default_labels: Any,
    ) -> DockerSwarm:
        """
        Configures Worker nodes on the Swarm.

        Parameters
        ----------
        hosts
            A mapping from AinurHosts to dictionaries of labels.
        default_labels
            All other keyword arguments are treated as default values for
            labels.

        Returns
        -------
        self
            For chaining.
        """

        try:
            mgr_node = self._manager_nodes.pop()
            self._manager_nodes.add(mgr_node)
            with ThreadPoolExecutor() as tpool:
                # use thread pool instead of process pool, as we only really
                # need I/O concurrency (Docker client comms) and threads are
                # much more lightweight than processes
                exc_lock = threading.RLock()
                caught_exceptions = deque()

                def _add_worker(h_l: Tuple[AinurHost, Dict]) -> None:
                    host, host_labels = h_l
                    labels = dict(default_labels)
                    labels.update(host_labels)
                    try:
                        node = mgr_node.attach_worker(
                            host=host, labels=labels, daemon_port=self._daemon_port
                        )
                        self._worker_nodes.add(node)
                    except Exception as e:
                        with exc_lock:
                            caught_exceptions.append(e)

                # NOTE: ThreadPoolExecutor.map does not block, as opposed to
                # ProcessPool.map; it immediately returns an iterator.
                # Here we force it to block by immediately exiting the with
                # block, which causes the pool to wait for all threads and
                # then shut down.
                tpool.map(_add_worker, hosts.items())

            if len(caught_exceptions) > 0:
                raise SwarmException(
                    f"Could not attach all nodes in " f"{hosts.keys()} to Swarm."
                ) from caught_exceptions.pop()

            return self
        except KeyError:
            # if no existing managers, we have a problem
            raise SwarmException(
                "No managers available in the Swarm, cannot " "deploy worker nodes!"
            )

    @property
    def num_nodes(self) -> int:
        """
        Returns
        -------
        int
            The number of nodes in this Swarm.
        """
        return len(self._manager_nodes) + len(self._worker_nodes)

    def __len__(self) -> int:
        return self.num_nodes

    @staticmethod
    def _tear_down(nodes: Collection[SwarmNode]):
        with ThreadPoolExecutor() as tpool:

            def leave_swarm(node: SwarmNode) -> None:
                node.leave_swarm(force=True)

                # NOTE: see comment about .map blocking further up.

            tpool.map(leave_swarm, nodes)

    def tear_down(self) -> None:
        """
        Convenience method to fully tear down this swarm.
        This object will be in an invalid state afterwards and should not be
        used any more.
        """

        logger.warning("Tearing down Swarm!")
        self._tear_down(self._worker_nodes)
        self._worker_nodes.clear()
        self._tear_down(self._manager_nodes)
        self._manager_nodes.clear()
        logger.warning("Swarm has been torn down.")

    def __enter__(self) -> DockerSwarm:
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
        """
        return frozenset(self._manager_nodes)

    @property
    def workers(self) -> FrozenSet[WorkerNode]:
        """
        Returns
        -------
        FrozenSet
            A view into the Worker nodes of this Swarm.
        """
        return frozenset(self._worker_nodes)

    def deploy_workload(
        self,
        specification: WorkloadSpecification,
        attach_volume: Optional[str] = None,
        health_check_poll_interval: float = 10.0,
        complete_threshold: int = 3,
        max_failed_health_checks: int = 3,
        ignored_health_services: Sequence[str] = (),
    ) -> WorkloadResult:
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

        # sanity check
        if self.num_nodes == 0:
            raise SwarmException(
                "Cannot deploy a workload to a Docker Swarm "
                "that has not been deployed."
            )

        logger.info(f"Deploying workload {specification.name}:\n" f"{specification}")

        # TODO: figure out a way to pull images before deploying

        # calculate  time log formats before launching to not
        # interfere with actual duration
        max_duration = timeparse.timeparse(
            specification.max_duration, granularity="seconds"
        )
        max_dur_hms = seconds2hms(max_duration)
        health_ival_hms = seconds2hms(health_check_poll_interval)

        log_max_fails = (
            max_failed_health_checks if max_failed_health_checks > 0 else "∞"
        )

        logger.info(f"Max workload runtime: {max_dur_hms}")
        logger.info(
            f"Health check interval: {health_ival_hms}; maximum "
            f"allowed failed health checks: {log_max_fails}."
        )
        if len(ignored_health_services) > 0:
            logger.warning(
                f"Ignoring health status of services: {ignored_health_services}"
            )
            ignored_health_services = {
                f"{specification.name}_{name}" for name in ignored_health_services
            }

        with specification.temp_compose_file(attach_volume) as compose_file:
            logger.debug(f"Using temporary docker-compose v3 at " f"{compose_file}.")

            # we use python-on-whales to deploy the service stack,
            # since docker-py is too low-level.

            # grab an arbitrary manager and point a client to it
            mgr_node = next(iter(self._manager_nodes))
            host_addr = f"{mgr_node.host.management_ip.ip}:" f"{mgr_node.daemon_port}"

            try:
                stack = WhaleClient(host=host_addr).stack.deploy(
                    name=specification.name,
                    compose_files=[compose_file],
                    orchestrator="swarm",
                )
            except DockerException as e:
                logger.exception(
                    "Caught exception when deploying workload "
                    "service stack to Swarm.",
                    e,
                )
                raise e

            # TODO: environment files
            # TODO: variables in compose? really useful!
            # TODO: logging. could be handled here instead of in fluentbit

            # convert the python-on-whales service objects into pure
            # Docker-Py Service objects for more efficient health checks

            with mgr_node.client_context() as client:
                services = []
                ignored_services = []

                for s in stack.services():
                    serv = client.services.get(s.id)
                    if serv.name in ignored_health_services:
                        ignored_services.append(serv)
                    else:
                        services.append(serv)

                # services = [client.services.get(s.id) for s in stack.services()]

            logger.warning(
                f"Workload {specification.name} "
                f"({len(services)} services) has been deployed!"
            )

            # start health checks and countdown to max duration
            # thread functions
            # ----------------
            timed_out = threading.Event()
            status_cond = threading.Condition()

            def _wkld_timeout():
                logger.warning(f"Workload {specification.name} timed out!")
                with status_cond:
                    timed_out.set()
                    status_cond.notify_all()

            # ----------------

            timeout_timer = threading.Timer(
                interval=max_duration, function=_wkld_timeout
            )
            timeout_timer.start()

            health_check_timer = ServiceHealthCheckThread(
                shared_condition=status_cond,
                services=services,
                check_interval=health_check_poll_interval,
                complete_thresh=complete_threshold,
                max_failed_health_checks=max_failed_health_checks,
                ignored_services=ignored_services,
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

                logger.warning(
                    "Tearing down Docker Swarm service "
                    f"stack for workload {specification.name}."
                )
                stack.remove()

            return result
