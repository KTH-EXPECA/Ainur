import os
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from pathlib import Path

from ainur import AnsibleContext
from ainur.cloud.aws import aws_instance_ctx
from ainur.cloud.vpn import VPNGatewayConfig, vpn_mesh_context

if __name__ == '__main__':
    # first create some AWS instances
    with aws_instance_ctx(3) as aws_instances:
        # next, deploy a VPN mesh across them all
        with vpn_mesh_context(
                hosts=aws_instances,
                gw_config=VPNGatewayConfig(
                    public_ip=IPv4Address('130.237.53.70'),
                    vpn_interface=IPv4Interface('172.16.0.1/24'),
                    vpn_psk=os.getenv('vpn_psk'),
                    local_network=IPv4Network('192.168.0.0/16'),
                    public_port=3210,
                ),
                ansible_quiet=True,
                ansible_ctx=AnsibleContext(
                    base_dir=Path('./ansible_env')
                ),
                vpn_network_name='expeca',
                vpncloud_port=3210,
        ) as mesh:
            print()
            for i in aws_instances:
                print(i)

            input('Press any key to tear down.')
