from __future__ import annotations

import abc
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager, contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Generator, Literal, Optional, \
    Set

from docker import DockerClient
from loguru import logger

from . import WorkloadNetwork
from .hosts import ConnectedWorkloadHost
from .workload import WorkloadDefinition


@contextmanager
def docker_client_context(*args, **kwargs) \
        -> Generator[DockerClient, None, None]:
    """
    Utility context manager which simply creates a DockerClient with the
    provided arguments, binds it to the 'as' argument, and makes sure to
    close it on exiting the context.

    Parameters
    ----------
    args

    kwargs

    Yields
    ------
    DockerClient
        An initialized Docker client instance.
    """
    client = DockerClient(*args, **kwargs)
    yield client
    client.close()


class SwarmWarning(Warning):
    pass


class SwarmException(Exception):
    pass


# Low-level API, do not expose

@dataclass
class _NodeSpec:
    Name: str
    Role: Literal['manager', 'worker']
    Labels: Dict[str, str] = field(default_factory={})
    Availability: str = field(default='active')

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass(frozen=True, eq=True)
class SwarmNode(abc.ABC):
    node_id: str
    swarm_id: str
    host: ConnectedWorkloadHost
    daemon_port: int
    is_manager: bool = field(default=False, init=False)

    @abc.abstractmethod
    def leave_swarm(self, force: bool = False) -> None:
        pass


@dataclass(frozen=True, eq=True)
class WorkerNode(SwarmNode):
    is_manager = False
    manager_host: ConnectedWorkloadHost

    def leave_swarm(self, force: bool = False) -> None:
        logger.info(f'Worker {self.host} is leaving the Swarm.')
        with docker_client_context(
                base_url=f'{self.host.management_ip.ip}:{self.daemon_port}') \
                as client:
            if not client.swarm.leave(force=force):
                raise SwarmException(f'{self.host} could not leave swarm.')
        logger.info(f'Host {self.host} has left the Swarm.')


@dataclass(frozen=True, eq=True)
class ManagerNode(SwarmNode):
    manager_token: str
    worker_token: str
    is_manager = True

    @classmethod
    def init_swarm(cls,
                   host: ConnectedWorkloadHost,
                   labels: Optional[Dict[str, str]] = None,
                   daemon_port: int = 2375) -> ManagerNode:
        """
        Initializes a new swarm and returns a ManagerNode attached to it.

        Parameters
        ----------
        host
        labels
        daemon_port

        Returns
        -------
        ManagerNode
            A manager attached to the newly created swarm.
        """

        # note that we connect from the management network, but the Swarm is
        # built on top of the workload network.
        with docker_client_context(
                base_url=f'{host.management_ip.ip}:{daemon_port}') as client:
            logger.info(f'Initializing a Swarm on host {host}.')
            # initialize the swarm
            # listen and advertise Swarm management on the management
            # network, but send data through the workload network.
            client.swarm.init(
                listen_addr=str(host.management_ip.ip),
                advertise_addr=str(host.management_ip.ip),
                data_path_addr=str(host.workload_ip.ip)
            )

            # save the first manager
            # get some contextual info from the client
            swarm_info = client.info()['Swarm']
            node_id = swarm_info['NodeID']

            cluster_id = swarm_info['Cluster']['ID']
            logger.info(f'Initialized Swarm with cluster ID: '
                        f'{cluster_id}')
            logger.info(f'Registered manager on Swarm, node ID: {node_id}')

            # extract tokens
            tokens = client.swarm.attrs['JoinTokens']
            worker_token = tokens['Worker']
            manager_token = tokens['Manager']

            logger.info(f'Swarm worker token: {worker_token}')
            logger.info(f'Swarm manager token: {manager_token}')

            # set node spec
            node_spec = _NodeSpec(
                Name=host.name,
                Role='manager',
                Labels=labels if labels is not None else {}
            )

            swarm_node = client.nodes.get(node_id)
            swarm_node.update(node_spec.to_dict())
            logger.info(f'Set node spec for {host}.')

        return ManagerNode(
            node_id=node_id,
            swarm_id=cluster_id,
            host=host,
            manager_token=manager_token,
            worker_token=worker_token,
            daemon_port=daemon_port
        )

    def _attach_host(self,
                     host: ConnectedWorkloadHost,
                     token: str,
                     node_spec: _NodeSpec,
                     daemon_port: int = 2375) -> str:
        logger.info(f'Attaching host {host} to swarm managed by {self.host}.')
        try:
            with docker_client_context(
                    base_url=f'{host.management_ip.ip}:{daemon_port}'
            ) as client:
                if not client.swarm.join(
                        remote_addrs=[str(self.host.management_ip.ip)],
                        join_token=token,
                        listen_addr=str(host.management_ip.ip),
                        advertise_addr=str(host.management_ip.ip),
                        data_path_addr=str(host.workload_ip.ip)
                ):
                    raise SwarmException(f'{host} could not join swarm.')

                # joined the swarm, get the node ID now
                node_id = client.info()['Swarm']['NodeID']
                logger.info(f'{host} joined the swarm, assigned ID: {node_id}.')

            # set the node spec, from the manager
            with docker_client_context(
                    base_url=f'{self.host.management_ip.ip}:{daemon_port}'
            ) as client:
                new_node = client.nodes.get(node_id)
                new_node.update(node_spec.to_dict())
                logger.info(f'Set node spec for {host}.')

            return node_id
        except:
            logger.critical(f'Failed to attach node {host} to the Swarm!')
            raise

    def attach_manager(self,
                       host: ConnectedWorkloadHost,
                       labels: Optional[Dict[str, str]] = None,
                       daemon_port: int = 2375) -> ManagerNode:
        node_spec = _NodeSpec(
            Name=host.name,
            Role='manager',
            Labels=labels if labels is not None else {}
        )
        node_id = self._attach_host(host, self.manager_token,
                                    node_spec, daemon_port)

        return ManagerNode(
            node_id=node_id,
            swarm_id=self.swarm_id,
            host=host,
            manager_token=self.manager_token,
            worker_token=self.worker_token,
            daemon_port=daemon_port
        )

    def attach_worker(self,
                      host: ConnectedWorkloadHost,
                      labels: Optional[Dict[str, str]] = None,
                      daemon_port: int = 2375) -> WorkerNode:
        node_spec = _NodeSpec(
            Name=host.name,
            Role='worker',
            Labels=labels if labels is not None else {}
        )
        node_id = self._attach_host(host, self.worker_token,
                                    node_spec, daemon_port)

        return WorkerNode(
            node_id=node_id,
            swarm_id=self.swarm_id,
            host=host,
            manager_host=self.host,
            daemon_port=daemon_port
        )

    def leave_swarm(self, force: bool = False) -> None:
        logger.info(f'Manager {self.host} is leaving the Swarm.')

        with docker_client_context(
                base_url=f'{self.host.management_ip.ip}:{self.daemon_port}') \
                as client:

            # raise a warning if we're the last manager
            manager_nodes = client.nodes.list(filters={'role': 'manager'})
            last_mgr = (len(manager_nodes) == 1)

            if not client.swarm.leave(force=force):
                raise SwarmException(f'{self.host} could not leave swarm.')

        logger.info(f'Host {self.host} has left the Swarm.')
        if last_mgr:
            warnings.warn(
                f'{self.host} was the last manager of Swarm {self.swarm_id}. '
                f'Swarm is now invalid!',
                SwarmWarning
            )

    @contextmanager
    def client_context(self) -> Generator[DockerClient, None, None]:
        with docker_client_context(
                base_url=f'{self.host.management_ip.ip}:{self.daemon_port}') \
                as client:
            yield client


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

        self._managers = manager_nodes
        self._workers = worker_nodes
        self._torn_down = False

    def _check(self) -> None:
        if self._torn_down:
            raise SwarmException('Swarm has been torn down.')

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
        manager, manager_id = self._managers.popitem()

        with ThreadPoolExecutor() as tpool:
            def leave_swarm(node: SwarmNode) -> None:
                node.leave_swarm(force=True)

            tpool.map(leave_swarm,
                      list(self._managers.values()) +
                      list(self._workers.values()))

        # final manager leaves
        manager.leave_swarm(force=True)

        self._workers.clear()
        self._managers.clear()
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

        mgr, mgr_id = self._managers.popitem()
        self._managers[mgr] = mgr_id

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
    def managers(self) -> Set[ManagerNode]:
        self._check()
        return set(self._managers.keys())

    @property
    def workers(self) -> Set[WorkerNode]:
        self._check()
        return set(self._workers.keys())

    def deploy_workload(self, definition: WorkloadDefinition) -> Any:
        pass