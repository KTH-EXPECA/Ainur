from ipaddress import IPv4Interface
from pathlib import Path

from frozendict import frozendict
from loguru import logger

from ainur import *
from ainur.workload import Workload, WorkloadProcessDefinition

if __name__ == '__main__':
    # quick test to verify network + swarm work

    ansible_ctx = AnsibleContext(base_dir=Path('./ansible_env'))

    # build up a workload network
    hosts = {
        IPv4Interface('10.0.0.1/16') : DisconnectedWorkloadHost(
            name='cloudlet',
            ansible_host='elrond.expeca',
            management_ip=IPv4Interface('192.168.1.4'),
            workload_nic='enp4s0'
        ),
        IPv4Interface('10.0.1.10/16'): DisconnectedWorkloadHost(
            name='client10',
            ansible_host='workload-client-10.expeca',
            management_ip=IPv4Interface('192.168.1.110'),
            workload_nic='eth0'
        ),
        IPv4Interface('10.0.1.11/16'): DisconnectedWorkloadHost(
            name='client11',
            ansible_host='workload-client-11.expeca',
            management_ip=IPv4Interface('192.168.1.111'),
            workload_nic='eth0'
        ),
        IPv4Interface('10.0.1.12/16'): DisconnectedWorkloadHost(
            name='client12',
            ansible_host='workload-client-12.expeca',
            management_ip=IPv4Interface('192.168.1.112'),
            workload_nic='eth0'
        ),
    }

    # bring up the network
    with WorkloadNetwork(hosts, ansible_ctx) as network:
        logger.warning('Network is up.')

        # bring up the swarm
        with DockerSwarm(network,
                         managers={'cloudlet'},
                         labels={}) as swarm:
            logger.warning('Swarm is up.')

            process_defs = set()
            for i, worker in enumerate(swarm.workers):
                server_proc = WorkloadProcessDefinition(
                    name='prime-server',
                    image='expeca/primeworkload',
                    tag='server',
                    nodes=swarm.managers,
                    environment=frozendict(PORT=5000)
                )

                client_proc = WorkloadProcessDefinition(
                    name='prime-client',
                    image='expeca/primeworkload',
                    tag='client',
                    nodes={worker},
                    environment=frozendict(SERVER_ADDR=server_proc.service_name,
                                           SERVER_PORT=5000)
                )
                process_defs.update({server_proc, client_proc})

            workload = Workload(
                name=f'TestWorkload-{i}',
                duration='30s',
                process_defs=process_defs,
            )
            workload.deploy_to_swarm(swarm)

        logger.warning('Swarm is down.')

        # swarm is down

    logger.warning('Network is down.')
    # network is down
