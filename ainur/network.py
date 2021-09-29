import functools
from collections import Mapping
from dataclasses import dataclass
from ipaddress import IPv4Interface, IPv4Network
from pathlib import Path
from typing import Tuple

import ansible_runner

from ainur.hosts import ConnectedWorkloadHost, DisconnectedWorkloadHost
from ainur.util import ansible_temp_dir


@dataclass(frozen=True, eq=True)
class WorkloadNetwork:
    network_addr: IPv4Network
    hosts: Tuple[ConnectedWorkloadHost]


def build_workload_network(
        ip_hosts: Mapping[IPv4Interface, DisconnectedWorkloadHost],
        playbook_dir: Path) -> WorkloadNetwork:
    # TODO: document

    # NOTE: mapping is ip -> host, and not host -> ip, since ip addresses are
    # unique in a network but a host may have more than one ip.

    # sanity check: all the addresses should be in the same subnet
    if not functools.reduce(lambda l, r: l == r, [k.network for k in ip_hosts]):
        raise RuntimeError('Provided IPv4 interfaces should all belong to the '
                           'same network.')

    # build an Ansible inventory
    inventory = {
        'all': {
            'hosts': {
                host.name: {
                    'ansible_host': host.ansible_host,
                    'workload_nic': host.workload_nic,
                    'workload_ip' : str(interface)  # {ip}/{netmask}
                } for interface, host in ip_hosts.items()
            }
        }
    }

    # prepare a temp ansible environment and run the appropriate playbook
    with ansible_temp_dir(
            inventory=inventory,
            playbooks=['net_up.yml'],
            base_playbook_dir=playbook_dir
    ) as tmp_dir:
        res = ansible_runner.run(
            playbook='net_up.yml',
            json_mode=True,
            private_data_dir=str(tmp_dir),
            quiet=True,
        )

        # TODO: better error checking
        assert res.status != 'failed'

        # network is now up and running
        return WorkloadNetwork(
            network_addr=list(ip_hosts.keys())[0].network,
            hosts=tuple([
                ConnectedWorkloadHost(
                    name=h.name,
                    ansible_host=h.ansible_host,
                    workload_nic=h.workload_nic,
                    workload_ip=i
                )
                for i, h in ip_hosts.items()
            ])
        )
