from ipaddress import IPv4Interface
from pathlib import Path

from ainur import *

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
        # bring up the swarm
        with DockerSwarm(network, managers=['cloudlet']) as swarm:
            with swarm.manager_client_ctx() as client:
                import pprint

                pprint.PrettyPrinter(indent=4).pprint(client.swarm.attrs)

        # swarm is down

    # network is down
