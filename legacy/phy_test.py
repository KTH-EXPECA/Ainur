#  Copyright (c) 2022 KTH Royal Institute of Technology, Sweden,
#  and the ExPECA Research Group (PI: Prof. James Gross).
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from ipaddress import IPv4Interface
from pathlib import Path

from ainur import *

if __name__ == '__main__':
    # quick test to verify network + swarm work

    inventory = {
        'hosts' : {
            'workload-client-04': WorkloadHost(
                ansible_host='workload-client-04',
                management_ip=IPv4Interface('192.168.1.104/24'),
                interfaces={'eth0': EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:53:b8',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=29),
                ),
                },
            ),
            'workload-client-05': WorkloadHost(
                ansible_host='workload-client-05',
                management_ip=IPv4Interface('192.168.1.105/24'),
                interfaces={'eth0': EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:07:fe:f2',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=30),
                ),
                },
            ),
            'workload-client-06': WorkloadHost(
                ansible_host='workload-client-06',
                management_ip=IPv4Interface('192.168.1.106/24'),
                interfaces={'eth0': EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:53:f4',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=31),
                ),
                },
            ),
            'workload-client-07': WorkloadHost(
                ansible_host='workload-client-07',
                management_ip=IPv4Interface('192.168.1.107/24'),
                interfaces={'eth0': EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:52:83',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=32),
                ),
                },
            ),
            'workload-client-08': WorkloadHost(
                ansible_host='workload-client-08',
                management_ip=IPv4Interface('192.168.1.108/24'),
                interfaces={'eth0': EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:54:12',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=33),
                ),
                    'wlan0'       : WiFiInterface(
                        name='wlan0',
                        mac='f0:2f:74:63:5c:d9',
                    ),
                },
            ),
            'workload-client-09': WorkloadHost(
                ansible_host='workload-client-09',
                management_ip=IPv4Interface('192.168.1.109/24'),
                interfaces={'eth0': EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:53:40',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=34),
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

    # build up the workload networks
    # channels: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 36, 40, 44, 48]
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
            'workload-client-07': {'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.0.7/24'),
                phy=WiFi(network='wlan_net', radio='RFSOM-00002', is_ap=True),
            ),
            },
            'workload-client-08': {'wlan0': ConnectionSpec(
                ip=IPv4Interface('10.0.0.8/24'),
                phy=WiFi(network='wlan_net', radio='native', is_ap=False),
            ),
            },
            'workload-client-09': {'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.0.9/24'),
                phy=WiFi(network='wlan_net', radio='RFSOM-00001', is_ap=False),
            ),
            },
            'workload-client-04': {'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.1.4/24'),
                phy=Wire(network='eth_net'),
            ),
            },
            'workload-client-05': {'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.1.5/24'),
                phy=Wire(network='eth_net'),
            ),
            },
            'workload-client-06': {'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.1.6/24'),
                phy=Wire(network='eth_net'),
            ),
            },
        }
    }

    ansible_ctx = AnsibleContext(base_dir=Path('../ansible_env'))

    # Start phy layer
    with PhysicalLayer(inventory, workload_network_desc, ansible_ctx,
                       ansible_quiet=True) as phy_layer:
        input("Press Enter to continue...")
