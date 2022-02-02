from ipaddress import IPv4Interface
from pathlib import Path

import yaml

from ainur import *

inventory = {
    'hosts' : {
        'workload-client-00': WorkloadHost(
            ansible_host='workload-client-00',
            management_ip=IPv4Interface('192.168.1.100/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:b4:d8:b5',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=25),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='7c:10:c9:1c:3f:f0',
                ),
            },
        ),
        'workload-client-01': WorkloadHost(
            ansible_host='workload-client-01',
            management_ip=IPv4Interface('192.168.1.101/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:53:04',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=26),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='7c:10:c9:1c:3f:ea',
                ),
            },
        ),
        'workload-client-02': WorkloadHost(
            ansible_host='workload-client-02',
            management_ip=IPv4Interface('192.168.1.102/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:52:95',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=27),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='7c:10:c9:1c:3f:e8',
                ),
            },
        ),
        'workload-client-03': WorkloadHost(
            ansible_host='workload-client-03',
            management_ip=IPv4Interface('192.168.1.103/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:52:a1',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=28),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='7c:10:c9:1c:3e:04',
                ),
            },
        ),
        'workload-client-04': WorkloadHost(
            ansible_host='workload-client-04',
            management_ip=IPv4Interface('192.168.1.104/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:53:b8',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=29),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='fc:34:97:25:a1:9b',
                ),
            },
        ),
        'workload-client-05': WorkloadHost(
            ansible_host='workload-client-05',
            management_ip=IPv4Interface('192.168.1.105/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:07:fe:f2',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=30),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='7c:10:c9:1c:3e:a8',
                ),
            },
        ),
        'workload-client-06': WorkloadHost(
            ansible_host='workload-client-06',
            management_ip=IPv4Interface('192.168.1.106/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:53:f4',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=31),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='fc:34:97:25:a2:92',
                ),
            },
        ),
        'workload-client-07': WorkloadHost(
            ansible_host='workload-client-07',
            management_ip=IPv4Interface('192.168.1.107/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:52:83',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=32),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='24:4b:fe:b7:26:92',
                ),
            },
        ),
        'workload-client-08': WorkloadHost(
            ansible_host='workload-client-08',
            management_ip=IPv4Interface('192.168.1.108/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:54:12',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=33),
                ),
                'wlan0': WiFiInterface(
                    name='wlan0',
                    mac='f0:2f:74:63:5c:d9',
                ),
            },
        ),
        'workload-client-09': WorkloadHost(
            ansible_host='workload-client-09',
            management_ip=IPv4Interface('192.168.1.109/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:53:40',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=34),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='3c:7c:3f:a2:50:bd',
                ),
            },
        ),
        'workload-client-10': WorkloadHost(
            ansible_host='workload-client-10',
            management_ip=IPv4Interface('192.168.1.110/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:52:b0',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=35),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='fc:34:97:25:a2:0d',
                ),
            },
        ),
        'workload-client-11': WorkloadHost(
            ansible_host='workload-client-11',
            management_ip=IPv4Interface('192.168.1.111/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:54:1b',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=36),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='7c:10:c9:16:17:2e',
                ),
            },
        ),
        'workload-client-12': WorkloadHost(
            ansible_host='workload-client-12',
            management_ip=IPv4Interface('192.168.1.112/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:52:b3',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=37),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='7c:10:c9:16:17:2d',
                ),
            },
        ),
        'elrond'            : WorkloadHost(
            ansible_host='elrond',
            management_ip=IPv4Interface('192.168.1.4/24'),
            interfaces={
                'enp4s0': EthernetInterface(
                    name='enp4s0',
                    mac='d8:47:32:a3:25:20',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=2),
                )
            },
        )
    },
    'radios': {
        'RFSOM-00001': SoftwareDefinedRadio(
            name='RFSOM-00001',
            mac='02:05:f7:80:0b:72',
            management_ip=IPv4Interface('192.168.1.61/24'),
            switch_connection=SwitchConnection(name='glorfindel', port=41)
        ),
        'RFSOM-00002': SoftwareDefinedRadio(
            name='RFSOM-00002',
            mac='02:05:f7:80:0b:19',
            management_ip=IPv4Interface('192.168.1.62/24'),
            switch_connection=SwitchConnection(name='glorfindel', port=42)
        ),
        'RFSOM-00003': SoftwareDefinedRadio(
            name='RFSOM-00003',
            mac='02:05:f7:80:02:c8',
            management_ip=IPv4Interface('192.168.1.63/24'),
            switch_connection=SwitchConnection(name='glorfindel', port=43)
        ),
    },
    'switch': Switch(
        name='glorfindel',
        management_ip='192.168.1.5/24',
        username='cisco',
        password='expeca',
    ),
}

# TODO: connection spec should not include IP addresses, as this mixes the
#  layers.
# TODO: connection spec needs to be simplified to match phy!
workload_network_desc = {
    'subnetworks'     : {
        'wlan_net': WiFiNetwork(
            name='wlan_net',
            ssid='expeca_wlan_1',
            channel=11,
            beacon_interval=100,
            ht_capable=True,
        ),
        'eth_net' : WiredNetwork(
            name='eth_net',
        ),
    },
    'connection_specs': {
        'workload-client-00'   : {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.0/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-01'   : {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.1/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-02'   : {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.2/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-03'   : {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.3/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        }, 'workload-client-04': {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.4/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-05'   : {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.5/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-06'   : {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.6/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-07'   : {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.7/16'),
                # phy=Wire(network='eth_net')
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-08'   : {
            'wlan0': ConnectionSpec(
                ip=IPv4Interface('10.0.1.8/16'),
                # phy=Wire(network='eth_net')
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-09'   : {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.9/16'),
                # phy=Wire(network='eth_net')
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-10'   : {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.10/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-11'   : {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.11/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-12'   : {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.12/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'elrond'               : {
            'enp4s0': ConnectionSpec(
                ip=IPv4Interface('10.0.0.1/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='RFSOM-00002', is_ap=True)
            ),
        },
    }
}

if __name__ == '__main__':
    ansible_ctx = AnsibleContext(base_dir=Path('../ansible_env'))
    conn_specs = workload_network_desc['connection_specs']

    # Start phy layer
    with PhysicalLayer(inventory,
                       workload_network_desc,
                       ansible_ctx,
                       ansible_quiet=True) as phy_layer:
        host_ips = {}
        for host_name, host in phy_layer.items():
            conn_spec = conn_specs[host_name][host.workload_interface]
            host_ips[host_name] = conn_spec.ip

        with LANLayer(
                network_cfg=workload_network_desc['subnetworks'],
                host_ips=host_ips,
                layer2=phy_layer,
                ansible_context=ansible_ctx,
                ansible_quiet=True
        ) as workload_net:
            input("Press Enter to continue...")
