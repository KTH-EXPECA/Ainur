from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, FrozenSet, Mapping, Optional, Tuple

from docker import DockerClient
from docker.models.networks import Network
from frozendict import frozendict
from loguru import logger

from .swarm import DockerSwarm, SwarmNode


@dataclass(frozen=True, eq=True)
class WorkloadServiceDefinition:
    name: str
    image: str
    environment: frozendict = field(default_factory=frozendict)


@dataclass(frozen=True, eq=True)
class WorkloadDefinition:
    name: str
    max_duration: str = '1d'
    clients: frozendict = field(default_factory=frozendict)
    servers: frozendict = field(default_factory=frozendict)

    # TODO include fluentbit container here somewhere?


@dataclass(frozen=True, eq=True)
class WorkloadProcessDefinition:
    name: str
    image: str
    nodes: FrozenSet[SwarmNode]
    environment: Mapping[str, Any] = field(default_factory=frozendict)
    tag: str = field(default='latest')
    service_name: str = field(init=False,
                              default_factory=lambda: str(uuid.uuid4()))

    # TODO: log_driver
    # TODO: bunch of options
    # TODO: use Docker swarm scaling??
    # TODO: use labels for deploying

    def deploy(self,
               client: DockerClient,
               network: Network) -> Tuple[WorkloadProcess]:
        services: Deque[WorkloadProcess] = deque()
        for swarm_node in self.nodes:
            serv = client.services.create(
                image=f'{self.image}:{self.tag}',
                name=self.service_name,
                labels={'name': self.name},
                env=dict(self.environment),
                constraints=[f'node.id=={swarm_node.node_id}'],
                maxreplicas=1,
                networks=[network.id]
            )
            logger.info(f'Deployed workload process {self.name} '
                        f'(service name {self.service_name} on Docker Swarm '
                        f'node {swarm_node}.')
            services.append(WorkloadProcess(self, self.service_name, serv.id))

        return tuple(services)


@dataclass(frozen=True, eq=True)
class WorkloadProcess:
    definition: WorkloadProcessDefinition
    name: str
    service_id: str

    def tear_down(self, client: DockerClient) -> None:
        logger.info(f'Tearing down workload process {self.name} with service '
                    f'id {self.service_id}.')

        # get the Service object from the client
        service = client.services.get(self.service_id)
        service.remove()

        logger.warning('Workload process {self.name} with service '
                       f'id {self.service_id} has been torn down.')


@dataclass(frozen=True, eq=True)
class Workload:
    name: str
    duration: str
    process_defs: FrozenSet[WorkloadProcessDefinition]
    id: uuid.UUID = field(init=False, default_factory=uuid.uuid4)

    def deploy_to_swarm(self, swarm: DockerSwarm) -> None:
        logger.info(f'Deploying workload {self.name} ({self.id}) to swarm '
                    f'{swarm.id}')

        running_procs: Deque[WorkloadProcess] = deque()
        with swarm.manager_client_ctx() as client:
            logger.info(f'Creating exclusive overlay network for workload...')

            # TODO: move this somewhere else
            max_name_len = 62 - len(str(uuid.uuid4()))

            net_name = f'{self.name[:max_name_len]}-{uuid.uuid4()}'
            workload_overlay_net = client.networks.create(
                name=net_name,
                driver='overlay',
                check_duplicate=True,
                internal=True,
                scope='swarm'
            )

            logger.info(f'Created exclusive overlay network {net_name}.')

            # TODO: synchronize start
            for proc_def in self.process_defs:
                running_procs.extend(proc_def.deploy(client,
                                                     workload_overlay_net))

        # TODO: remove this ffs
        # TODO: JUST FOR DEMO
        # time.sleep(tparse(self.duration, granularity='seconds'))
        input('Press any key to exit.')
        with swarm.manager_client_ctx() as client:
            for rproc in running_procs:
                rproc.tear_down(client)

            network = client.networks.get(workload_overlay_net.id)
            network.remove()

            logger.info(f'Removed exclusive overlay network {net_name}.')

        logger.info(f'Workload {self.name} ({self.id}) on swarm '
                    f'{swarm.id}: DONE')
