from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Set, Tuple

from docker import DockerClient
from frozendict import frozendict
from loguru import logger
from pytimeparse import parse as tparse

from .swarm import DockerSwarm, SwarmNode


@dataclass(frozen=True, eq=True)
class WorkloadProcessDefinition:
    name: str
    image: str
    nodes: Set[SwarmNode]
    environment: frozendict = field(default=frozendict())
    tag: str = field(default='latest')
    service_name: str = field(init=False, default_factory=uuid.uuid4)

    # TODO: log_driver
    # TODO: bunch of options
    # TODO: use Docker swarm scaling??
    # TODO: use labels for deploying

    def deploy(self, client: DockerClient) -> Tuple[WorkloadProcess]:
        services: Deque[WorkloadProcess] = deque()
        for swarm_node in self.nodes:
            serv = client.services.create(
                image=self.image,
                name=self.service_name,
                labels={'name': self.name},
                env=self.environment,
                constraints=[f'node.id=={swarm_node.node_id}'],
                maxreplicas=1
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
    process_defs: Set[WorkloadProcessDefinition]
    id: uuid.UUID = field(init=False, default_factory=uuid.uuid4())

    def deploy_to_swarm(self, swarm: DockerSwarm) -> None:
        logger.info(f'Deploying workload {self.name} ({self.id}) to swarm '
                    f'{swarm.id}')

        running_procs: Deque[WorkloadProcess] = deque()
        with swarm.manager_client_ctx() as client:
            # TODO: synchronize start
            for proc_def in self.process_defs:
                running_procs.extend(proc_def.deploy(client))

        # TODO: remove this ffs
        # TODO: JUST FOR DEMO
        time.sleep(tparse(self.duration, granularity='seconds'))
        with swarm.manager_client_ctx() as client:
            for rproc in running_procs:
                rproc.tear_down(client)

        logger.info(f'Workload {self.name} ({self.id}) on swarm '
                    f'{swarm.id}: DONE')
