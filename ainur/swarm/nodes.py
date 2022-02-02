from __future__ import annotations

import abc
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Generator, Literal, Optional

from dataclasses_json import dataclass_json
from docker import DockerClient
from frozendict import frozendict
from loguru import logger

from .errors import SwarmException, SwarmWarning
from ..hosts import AinurHost
from ..misc import docker_client_context


# Low-level API, do not expose
@dataclass_json
@dataclass(frozen=True, eq=True)
class _NodeSpec:
    # Name: str
    Role: Literal['manager', 'worker']
    Labels: frozendict[str, str] = field(default_factory=frozendict)
    Availability: str = field(default='active')


@dataclass(frozen=True, eq=True)
class SwarmNode(abc.ABC):
    node_id: str
    swarm_id: str
    host: AinurHost
    daemon_port: int
    is_manager: bool = field(default=False, init=False)

    @abc.abstractmethod
    def leave_swarm(self, force: bool = False) -> None:
        pass


@dataclass(frozen=True, eq=True)
class WorkerNode(SwarmNode):
    is_manager = False
    manager_host: AinurHost

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
                   host: AinurHost,
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
                data_path_addr=str(host.workload_ips[0])
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
                Role='manager',
                Labels=frozendict(labels) if labels is not None else {}
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
                     host: AinurHost,
                     token: str,
                     node_spec: _NodeSpec,
                     daemon_port: int = 2375) -> str:
        logger.info(f'Attaching host {host} to swarm managed by {self.host}.')
        logger.debug(f'Applying node spec:\n{node_spec.to_json(indent=4)}')
        try:
            with docker_client_context(
                    base_url=f'{host.management_ip.ip}:{daemon_port}'
            ) as client:
                if not client.swarm.join(
                        remote_addrs=[str(self.host.management_ip.ip)],
                        join_token=token,
                        listen_addr=str(host.management_ip.ip),
                        advertise_addr=str(host.management_ip.ip),
                        data_path_addr=str(host.workload_ips[0])
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
        except Exception:
            logger.critical(f'Failed to attach node {host} to the Swarm!')
            raise

    def attach_manager(self,
                       host: AinurHost,
                       labels: Optional[Dict[str, str]] = None,
                       daemon_port: int = 2375) -> ManagerNode:
        node_spec = _NodeSpec(
            Role='manager',
            Labels=frozendict(labels) if labels is not None else {}
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
                      host: AinurHost,
                      labels: Optional[Dict[str, str]] = None,
                      daemon_port: int = 2375) -> WorkerNode:
        node_spec = _NodeSpec(
            Role='worker',
            Labels=frozendict(labels) if labels is not None else {}
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
