from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address
from pathlib import Path
from typing import Collection

import ansible_runner
from loguru import logger

from ainur import AnsibleContext


@dataclass(frozen=True, eq=True)
class VPNNodeConfig:
    host: IPv4Address | str
    vpn_addr: IPv4Address


def create_vpn_mesh(
        nodes: Collection[VPNNodeConfig],
        ansible_context: AnsibleContext,
        psk: str = 'vpnpsk',
        ansible_quiet: bool = True,
) -> None:

    # build an inventory for ansible
    # every node is a peer of each other node
    inventory = {
        'all': {
            'hosts': {
                str(node.host): {
                    'ansible_host': str(node.host),
                    'vpn_psk': psk,
                    'vpn_ip_addr': str(node.vpn_addr),
                    'vpn_peers': [str(other.host) for other in nodes
                                  if other != node]
                } for node in nodes
            }
        }
    }

    with ansible_context(inventory) as tmp_dir:
        logger.info(f'Deploying VPN mesh across {nodes}')
        res = ansible_runner.run(
            playbook='vpncloud_up.yml',
            json_mode=True,
            private_data_dir=str(tmp_dir),
            quiet=ansible_quiet
        )

        assert res.status != 'failed'

    logger.warning('VPNCloud deployed.')


if __name__ == '__main__':
    # quick test
    nodes = [
        VPNNodeConfig(
            host='ec2-13-51-171-254.eu-north-1.compute.amazonaws.com',
            vpn_addr=IPv4Address('10.0.0.1')
        ),
        VPNNodeConfig(
            host='ec2-13-53-35-80.eu-north-1.compute.amazonaws.com',
            vpn_addr=IPv4Address('10.0.0.2')
        )
    ]

    create_vpn_mesh(nodes,
                    ansible_context=AnsibleContext(
                        base_dir=Path('../ansible_env')
                    ),
                    ansible_quiet=False)
