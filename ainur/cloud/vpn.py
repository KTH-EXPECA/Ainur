import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from typing import Collection, Generator, Iterator

import ansible_runner
from loguru import logger

from ainur import AnsibleContext
from .hosts import EC2Host


# VPN:
# two networks, different ports
# All AWS nodes connect through each other through their VPC ips
# All AWS nodes connect to the management vpn gateway and the workload vpn gw

@dataclass(frozen=True, eq=True)
class VPNNetwork:
    pass


@dataclass(frozen=True, eq=True)
class VPNGatewayConfig:
    """
    Represents a VPN gateway config
    """

    public_ip: IPv4Address
    vpn_interface: IPv4Interface
    vpn_psk: str
    local_network: IPv4Network
    public_port: int = 3210

    @property
    def vpn_ip(self) -> IPv4Address:
        return self.vpn_interface.ip

    @property
    def vpn_network(self) -> IPv4Network:
        return self.vpn_interface.network

    @property
    def vpn_host_string(self) -> str:
        return f'{self.public_ip}:{self.public_port}'

    def vpn_node_addrs(self, excluded_ips: Collection[IPv4Address]) \
            -> Iterator[IPv4Interface]:
        excluded_ips = map(lambda ip: IPv4Interface(ip).ip, excluded_ips)
        for address in self.vpn_interface.network.hosts():
            if address in excluded_ips or address == self.vpn_interface.ip:
                continue
            yield IPv4Interface(f'{address}/{self.vpn_interface.netmask}')


class VPNConfigError(Exception):
    pass


@contextmanager
def vpn_mesh_context(
        hosts: Collection[EC2Host],
        gw_config: VPNGatewayConfig,
        ansible_ctx: AnsibleContext,
        vpn_network_name: str = str(uuid.uuid4().hex),
        vpncloud_port: int = 3210,
        excluded_vpn_ips: Collection[IPv4Address] = (),
        ansible_quiet: bool = True,
) -> Generator[VPNNetwork, None, None]:
    """
    Context manager for VPN mesh.

    Parameters
    ----------
    hosts
        AWS EC2 hosts to include in the mesh.
    gw_config
        A VPNGatewayConfig describing the VPN and the local gateway.
    ansible_ctx
        Ansible context for playbook execution.
    vpn_network_name
        The systemd name to give the VPN network on the nodes.
    vpncloud_port
        The port on which VPNCloud will be listening.
    excluded_vpn_ips
        IPs to exclude from the automatic assigment.
    ansible_quiet
        Silence Ansible output.

    Returns
    -------

    """

    # build an inventory for ansible
    # every node is a peer of each other node through their VPC addresses,
    # and every node is also a peer of the gateway through their public
    # addresses
    vpn_addresses = gw_config.vpn_node_addrs(excluded_vpn_ips)

    inventory = {
        'all': {
            'hosts': {
                host.instance_id: {
                    'ansible_host'  : str(host.public_ip),
                    'vpn_psk'       : gw_config.vpn_psk,
                    'vpn_ip'        : str(next(vpn_addresses).ip),
                    'vpn_net_name'  : vpn_network_name,
                    'vpn_peers'     : [gw_config.vpn_host_string] + [
                        other.vpc_vpn_host_string for other in hosts
                        if other != host
                    ],
                    'vpn_port'      : vpncloud_port,
                    'vpn_gw_local_net': str(gw_config.local_network),
                    'vpn_gw_ip'     : str(gw_config.vpn_interface.ip)
                }
                for host in hosts
            }
        }
    }

    with ansible_ctx(
            inventory=inventory,
            # TODO: hardcoded extravars are not nice...
            extravars={
                'ansible_user': 'ubuntu',
                'remote_user' : 'ubuntu',
            }
    ) as tmp_dir:
        res = ansible_runner.run(
            playbook='vpncloud_up.yml',
            json_mode=True,
            private_data_dir=str(tmp_dir),
            quiet=ansible_quiet
        )

        assert res.status != 'failed'

    logger.warning('VPN mesh layer deployed.')

    # TODO build a VPN network object
    try:
        yield None
    finally:
        # shut down VPN
        with ansible_ctx(
                inventory=inventory,
                # TODO: hardcoded extravars are not nice...
                extravars={
                    'ansible_user': 'ubuntu',
                    'remote_user' : 'ubuntu',
                }
        ) as tmp_dir:
            res = ansible_runner.run(
                playbook='vpncloud_down.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=ansible_quiet
            )

            assert res.status != 'failed'

        logger.warning('VPN mesh layer torn down.')
