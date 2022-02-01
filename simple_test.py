import os
from contextlib import ExitStack
from pathlib import Path

# from ainur import *
from ainur import AnsibleContext, NetworkLayer, PhysicalLayer
from ainur.cloud.aws import CloudLayer
from ainur.cloud.vpn import VPNCloudMesh
from ainur.hosts import *

switch = Switch(
    name='glorfindel',
    management_ip=IPv4Interface('192.168.0.2/16'),
    username='cisco',
    password='expeca',
)

# sdr_network = SDRWiFiNetwork(
#     ssid='expeca_wlan_1',
#     channel=11,
#     beacon_interval=100,
#     ht_capable=True,
#     access_point=SoftwareDefinedRadio(
#         name='RFSOM-00002',
#         management_ip=IPv4Interface('192.168.4.2/16'),
#         mac='02:05:f7:80:0b:19',
#         switch_port=42,
#     ),
#     stations=(
#         SoftwareDefinedRadio(
#             name='RFSOM-00001',
#             management_ip=IPv4Interface('192.168.4.1/16'),
#             mac='02:05:f7:80:0b:72',
#             switch_port=41,
#         ),
#         SoftwareDefinedRadio(
#             name='RFSOM-00003',
#             management_ip=IPv4Interface('192.168.4.3/16'),
#             mac='02:05:f7:80:02:c8',
#             switch_port=43
#         ),
#     )
# )

hosts = {
    'workload-client-00': LocalAinurHost(
        management_ip=IPv4Interface('192.168.3.0/16'),
        ethernets=frozendict({
            'eth0': EthernetCfg(
                ip_address=IPv4Interface('10.0.2.0/16'),
                routes=(
                    IPRoute(
                        to=IPv4Interface('172.16.1.0/24'),
                        via=IPv4Address('10.0.1.0')
                    ),
                ),
                mac='dc:a6:32:b4:d8:b5',
                wire_spec=WireSpec(
                    net_name='eth_net',
                    switch_port=25
                )
            ),
        }),
        wifis=frozendict()
    ),
    'workload-client-01': LocalAinurHost(
        management_ip=IPv4Interface('192.168.3.1/16'),
        ethernets=frozendict({
            'eth0': EthernetCfg(
                ip_address=IPv4Interface('10.0.2.1/16'),
                routes=(  # VPN route
                    IPRoute(
                        to=IPv4Interface('172.16.1.0/24'),
                        via=IPv4Address('10.0.1.0')
                    ),
                ),
                mac='dc:a6:32:bf:53:04',
                wire_spec=WireSpec(
                    net_name='eth_net',
                    switch_port=26
                )
            ),
        }),
        wifis=frozendict()
    ),
    # TODO: automatic way of configuring VPN gateway?
    'olwe'              : LocalAinurHost(
        management_ip=IPv4Interface('192.168.0.4/16'),
        ethernets=frozendict({
            'enp4s0': EthernetCfg(
                ip_address=IPv4Interface('10.0.1.0/16'),
                routes=(),
                mac='dc:a6:32:bf:54:1b',
                wire_spec=WireSpec(
                    net_name='eth_net',
                    switch_port=36,
                )
            )
        }),
        wifis=frozendict()
    ),
    'elrond'            : LocalAinurHost(
        management_ip=IPv4Interface('192.168.1.2/16'),
        ethernets=frozendict({
            'enp4s0': EthernetCfg(
                ip_address=IPv4Interface('10.0.1.1/16'),
                routes=(  # VPN route
                    IPRoute(
                        to=IPv4Interface('172.16.1.0/24'),
                        via=IPv4Address('10.0.1.0')
                    ),
                ),
                mac='d8:47:32:a3:25:20',
                wire_spec=WireSpec(
                    net_name='eth_net',
                    switch_port=2,
                )
            )
        }),
        wifis=frozendict()
    ),
}

cloud_hosts = [
    AinurCloudHostConfig(
        management_ip=IPv4Interface('172.16.0.2/24'),
        workload_ip=IPv4Interface('172.16.1.2/24')
    ),
    AinurCloudHostConfig(
        management_ip=IPv4Interface('172.16.0.3/24'),
        workload_ip=IPv4Interface('172.16.1.3/24')
    ),
    AinurCloudHostConfig(
        management_ip=IPv4Interface('172.16.0.4/24'),
        workload_ip=IPv4Interface('172.16.1.4/24')
    ),
]

# noinspection DuplicatedCode
if __name__ == '__main__':
    ansible_ctx = AnsibleContext(base_dir=Path('ansible_env'))

    with ExitStack() as stack:
        phy_layer: PhysicalLayer = stack.enter_context(
            PhysicalLayer(hosts, [], switch, ansible_ctx, ansible_quiet=True)
        )

        net_layer: NetworkLayer = stack.enter_context(
            NetworkLayer(layer2=phy_layer,
                         ansible_context=ansible_ctx,
                         ansible_quiet=False)
        )

        cloud: CloudLayer = stack.enter_context(CloudLayer())
        cloud.init_instances(len(cloud_hosts))

        vpn_mesh: VPNCloudMesh = stack.enter_context(
            VPNCloudMesh(
                gateway_ip=IPv4Address('130.237.53.70'),
                vpn_psk=os.environ['vpn_psk'],
                ansible_ctx=AnsibleContext(base_dir=Path('./ansible_env')),
                ansible_quiet=False
            )
        )
        vpn_mesh.connect_cloud(
            cloud_layer=cloud,
            host_configs=cloud_hosts
        )

        for host_id, host in vpn_mesh.items():
            print(host_id, host.to_json())

        input('Press any key to tear down.')
