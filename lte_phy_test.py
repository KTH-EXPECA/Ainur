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
        'elrond': WorkloadHost(
            ansible_host='elrond',
            management_ip=IPv4Interface('192.168.1.4/24'),
            interfaces={'enp4s0': EthernetInterface(
                name='enp4s0',
                mac='d8:47:32:a3:25:20',
                switch_connection=SwitchConnection(name='glorfindel',
                                                   port=2),
            )
            },
        )
    },
    'radiohosts': {
        'finarfin': WorkloadHost(
            ansible_host='finarfin',
            management_ip=IPv4Interface('192.168.1.52/24'),
            interfaces={'enp5s0': EthernetInterface(
                name='enp5s0',
                mac='00:d8:61:c6:1c:e1',
                switch_connection=SwitchConnection(name='glorfindel',
                                                   port=4),
                ),
            },
        ),
        'fingolfin': WorkloadHost(
            ansible_host='fingolfin',
            management_ip=IPv4Interface('192.168.1.51/24'),
            interfaces={'enp4s0': EthernetInterface(
                name='enp4s0',
                mac='00:d8:61:c6:1b:27',
                switch_connection=SwitchConnection(name='glorfindel',
                                                   port=3),
                ),
            },
        ),
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
workload_network_desc = {
    'subnetworks'     : {
        'lte_net' : LTENetwork(
            TAC='1',
            MNC='208',
            MCC='96',
            HPLMN= "20896",
            LTE_K='0c0a34601d4f07677303652c0462535b',
            OP_KEY='63bfa50ee6523365ff14c1f45f88737d',
            FIRST_MSIN='0010000001',
            MAX_N_UE=5,
            downlink_frequency=2680000000,
            uplink_frequency_offset=-120000000,
            eutra_band=7,
            N_RB_DL=25,
        ),
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
        'workload-client-07': {
            'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.0.7/24'),
                phy=WiFi(network='wlan_net', radio='RFSOM-00002', is_ap=True),
            ),
        },
        'workload-client-08': {
            'wlan0': ConnectionSpec(
                ip=IPv4Interface('10.0.0.8/24'),
                phy=WiFi(network='wlan_net', radio='native', is_ap=False),
            ),
        },
        'workload-client-09': {
            'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.0.9/24'),
                phy=WiFi(network='wlan_net', radio='RFSOM-00001', is_ap=False),
            ),
        },
        'workload-client-10': {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.0.10/24'),
                phy=WiFi(network='wlan_net', radio='native', is_ap=False),
            ),
        },
        'workload-client-04': {
            'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.1.4/24'),
                phy=Wire(network='eth_net'),
            ),
        },
        'workload-client-05': {
            'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.1.5/24'),
                phy=Wire(network='eth_net'),
            ),
        },
        'workload-client-06': {
            'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.1.6/24'),
                phy=Wire(network='eth_net'),
            ),
        },
        'elrond': {
            'enp4s0': ConnectionSpec(
                ip=IPv4Interface('10.0.2.1/24'),
                phy=LTE(network='lte_net', radio_host='finarfin', is_enb=True),
            ),
        },
        'workload-client-03': {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.2.3/24'),
                phy=LTE(network='lte_net', radio_host='fingolfin', is_enb=False),
            ),
        },
    }
}


if __name__ == '__main__':
    ansible_ctx = AnsibleContext(base_dir=Path('./ansible_env'))
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

        with NetworkLayer(
                network_cfg=workload_network_desc['subnetworks'],
                host_ips=host_ips,
                layer2=phy_layer,
                ansible_context=ansible_ctx,
                ansible_quiet=True
        ) as workload_net:
            input("Press Enter to continue...")
