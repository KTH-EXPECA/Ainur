from __future__ import annotations

import abc
import warnings
from contextlib import AbstractContextManager, contextmanager
from dataclasses import asdict, dataclass, field
from multiprocessing import Pool
from typing import Dict, Generator, Literal, Mapping, Set

from bidict import MutableBidirectionalMapping as BiDict, bidict
from docker import DockerClient
from loguru import logger

from .hosts import ConnectedWorkloadHost
from .network import WorkloadNetwork


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
    def leave_swarm(self) -> None:
        pass


@dataclass(frozen=True, eq=True)
class WorkerNode(SwarmNode):
    is_manager = False
    manager_host: ConnectedWorkloadHost

    def leave_swarm(self) -> None:
        logger.info(f'Worker {self.host} is leaving the Swarm.')
        with docker_client_context(
                base_url=f'{self.host.management_ip.ip}:{self.daemon_port}') \
                as client:
            if not client.swarm.leave():
                # TODO: custom exception here?
                raise RuntimeError(f'{self.host} could not leave swarm.')
        logger.info(f'Host {self.host} has left the Swarm.')


@dataclass(frozen=True, eq=True)
class ManagerNode(SwarmNode):
    manager_token: str
    worker_token: str
    is_manager = True

    @classmethod
    def init_swarm(cls,
                   host: ConnectedWorkloadHost,
                   labels: Dict[str, str],
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
                Labels=labels
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
                    # TODO: custom exception here?
                    raise RuntimeError(f'{host} could not join swarm.')

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
                       labels: Dict[str, str],
                       daemon_port: int = 2375) -> ManagerNode:
        node_spec = _NodeSpec(
            Name=host.name,
            Role='manager',
            Labels=labels
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
                      labels: Dict[str, str],
                      daemon_port: int = 2375) -> WorkerNode:
        node_spec = _NodeSpec(
            Name=host.name,
            Role='worker',
            Labels=labels
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

    def leave_swarm(self) -> None:
        logger.info(f'Manager {self.host} is leaving the Swarm.')

        with docker_client_context(
                base_url=f'{self.host.management_ip.ip}:{self.daemon_port}') \
                as client:

            # raise a warning if we're the last manager
            manager_nodes = client.nodes.list(filters={'role': 'manager'})
            last_mgr = (len(manager_nodes) == 1)

            if not client.swarm.leave(force=True):
                # TODO: custom exception here?
                raise RuntimeError(f'{self.host} could not leave swarm.')

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


# end of low-level API

class DockerSwarm(AbstractContextManager):
    """
    Implements an simple interface to a Docker swarm, built on top of a
    workload network. Can be used as a context manager, in which case the
    created instance is bound to the 'as' variable.

    Note that the Swarm is built up such that data traverses the workload
    network but management traffic stays on the management network.

    Example usage::

        with DockerSwarm(network, managers) as swarm:
            ...
            with swarm.manager_client_ctx() as client:
                client.services.ls()

            ...

    """

    _daemon_port = 2375

    def __init__(self,
                 network: WorkloadNetwork,
                 managers: Set[str],
                 labels: Mapping[str, str]):
        """
        Parameters
        ----------
        network
            The WorkloadNetwork on top of which to build this swarm.

        managers
            The name identifiers of the manager nodes.
        """

        super(DockerSwarm, self).__init__()

        logger.info(f'Setting up a Docker Swarm on top of workload network '
                    f'{network.address}.')

        # filter out the managers
        mgr_hosts = set([h for h in network.hosts if h.name in managers])
        workers = network.hosts.difference(mgr_hosts)

        logger.info(f'Docker Swarm manager hosts: '
                    f'{[h.workload_ip for h in mgr_hosts]}')

        # initialize some containers to store nodes
        # bidirectional mappings for future proofing
        self._managers: BiDict[ManagerNode, str] = bidict()
        self._workers: BiDict[WorkerNode, str] = bidict()

        # initialize the swarm on a arbitrary first manager,
        # make the others join afterwards
        try:
            first_mgr = mgr_hosts.pop()
        except KeyError:
            # TODO: custom exception?
            raise RuntimeError('Need at least one manager node!')

        # connect to the docker daemon on the node
        # note that we connect from the management network, but the Swarm is
        # built on top of the workload network.

        first_manager_node = ManagerNode.init_swarm(
            host=first_mgr,
            labels=labels.get(first_mgr.name, {}),
            daemon_port=self._daemon_port
        )

        self._id = first_manager_node.swarm_id
        self._managers[first_manager_node] = first_manager_node.node_id

        # add the rest of the nodes
        try:
            with Pool() as pool:
                new_managers = pool.starmap(
                    func=first_manager_node.attach_manager,
                    iterable=[(m, labels.get(m.name, {}), self._daemon_port)
                              for m in mgr_hosts]
                )

                new_workers = pool.starmap(
                    func=first_manager_node.attach_worker,
                    iterable=[(w, labels.get(w.name, {}), self._daemon_port)
                              for w in workers]

                )

                for nm in new_managers:
                    self._managers[nm] = nm.node_id

                for nw in new_workers:
                    self._workers[nw] = nw.node_id

            # for manager_host in mgr_hosts:
            #     new_manager = first_manager_node.attach_manager(
            #         host=manager_host,
            #         labels=labels.get(manager_host.name, {}),
            #         daemon_port=self._daemon_port
            #     )
            #     self._managers[new_manager] = new_manager.node_id
            #
            # for worker_host in workers:
            #     new_worker = first_manager_node.attach_worker(
            #         host=worker_host,
            #         labels=labels.get(worker_host.name, {}),
            #         daemon_port=self._daemon_port
            #     )
            #     self._workers[new_worker] = new_worker.node_id
        except:
            self.tear_down()
            raise

    @property
    def id(self) -> str:
        return self._id

    def tear_down(self) -> None:
        """
        Convenience method to fully tear down this swarm.
        This object will be in an invalid state afterwards and should not be
        used any more.
        """

        logger.warning('Tearing down Swarm!')

        # save a final manager to disconnect at the end, to ensure a
        # consistent state across the operation
        manager, manager_id = self._managers.popitem()

        with Pool() as pool:
            pool.map(WorkerNode.leave_swarm, self._workers.keys())
            pool.map(ManagerNode.leave_swarm, self._managers.keys())

        # final manager leaves
        manager.leave_swarm()

        # for worker in self._workers:
        #     worker.leave_swarm()
        #
        # for manager in self._managers:
        #     manager.leave_swarm()

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
        mgr, mgr_id = self._managers.popitem()
        self._managers[mgr] = mgr_id

        with mgr.client_context() as client:
            yield client

    def __enter__(self) -> DockerSwarm:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # on exit, we tear down this swarm
        self.tear_down()
        return super(DockerSwarm, self).__exit__(exc_type, exc_val, exc_tb)

    @property
    def managers(self) -> Set[ManagerNode]:
        return set(self._managers.keys())

    @property
    def workers(self) -> Set[WorkerNode]:
        return set(self._workers.keys())
