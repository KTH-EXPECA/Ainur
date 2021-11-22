from __future__ import annotations

import warnings
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Dict, FrozenSet, Generator

from docker import DockerClient
from frozendict import frozendict
from loguru import logger

from .errors import SwarmException, SwarmWarning
from .nodes import ManagerNode, SwarmNode, WorkerNode
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

    def __init__(self,
                 network: WorkloadNetwork,
                 managers: Dict[str, Dict[str, Any]],
                 workers: Dict[str, Dict[str, Any]]):

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
                            host=args['host'],
                            labels=args['labels'],
                            daemon_port=self._daemon_port
                        )
                        manager_nodes[args['id']] = node
                    else:
                        node = first_manager_node.attach_worker(
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

        # save a final manager to disconnect at the end, to ensure a
        # consistent state across the operation
        manager_id, manager = next(iter(self._managers.items()))

        with ThreadPoolExecutor() as tpool:
            def leave_swarm(node: SwarmNode) -> None:
                node.leave_swarm(force=True)

            # NOTE: see comment about .map blocking further up.
            tpool.map(leave_swarm,
                      list(self._managers.values()) +
                      list(self._workers.values()))

        # final manager leaves
        manager.leave_swarm(force=True)
        logger.warning('Swarm has been torn down.')

    @contextmanager
    def manager_client_ctx(self) -> Generator[DockerClient, None, None]:
        """
        Returns a Docker client to a manager node wrapped in a context manager.

        Example usage::

            with swarm.manager_client_ctx() as client:
                client.services.ls()

        Yields
        ------
        DockerClient
            A Docker client attached to an arbitrary manager node.
        """

        self._check()

        mgr_id, mgr = next(iter(self._managers.items()))
        with mgr.client_context() as client:
            yield client

    def __enter__(self) -> DockerSwarm:
        self._check()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # on exit, we tear down this swarm
        self.tear_down()
        return super(DockerSwarm, self).__exit__(exc_type, exc_val, exc_tb)

    @property
    def managers(self) -> FrozenSet[ManagerNode]:
        self._check()
        return frozenset(self._managers.values())

    @property
    def workers(self) -> FrozenSet[WorkerNode]:
        self._check()
        return frozenset(self._workers.keys())

    def deploy_workload(self) -> Any:
        pass
