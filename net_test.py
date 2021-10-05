from ipaddress import IPv4Interface
from pathlib import Path

from ainur import *


if __name__ == '__main__':
    # quick test to verify network + swarm work

    ansible_ctx = AnsibleContext(base_dir=Path('./ansible_env'))

    # build up a workload network
    hosts = {(
        IPv4Interface('10.0.0.7/24'), 
            SoftwareDefinedWiFiRadio(
                type_name='SDR_AP',
                sdr_name='RFSOM-00001',
                mac_addr='dc:a6:32:bf:54:13',
                ssid='ExpecaNetwork',
                preset=''
            )
        ) : WorkloadHost(
                name='cloudlet',
                ansible_host='workload-client-07',
                management_ip=IPv4Interface('192.168.1.107/24'),
                workload_interface=WorkloadInterface(
                    type_name='ethernets',
                    name='eth0',
                    mac_addr='dc:a6:32:bf:54:13',
                    switch=SwitchConnection(name='glorfindel',port='24')
                )
        ),(
        IPv4Interface('10.0.0.8/24'),
            WiFiRadio(
                type_name='NATIVE_STA',
                ssid='ExpecaNetwork',
                preset=''
            )
        ) : WorkloadHost(
                name='endnode1',
                ansible_host='workload-client-08',
                management_ip=IPv4Interface('192.168.1.108/24'),
                workload_interface=WorkloadInterface(
                    type_name='wifis',
                    name='wlan1',
                    mac_addr='dc:a6:32:bf:54:13',
                    switch=None
                )
        ),(
        IPv4Interface('10.0.0.9/24'),
            WiFiRadio(
                type_name='NATIVE_STA',
                ssid='ExpecaNetwork',
                preset=''
            )
        ) : WorkloadHost(
                name='endnode2',
                ansible_host='workload-client-09',
                management_ip=IPv4Interface('192.168.1.109/24'),
                workload_interface=WorkloadInterface(
                    type_name='wifis',
                    name='wlan1',
                    mac_addr='dc:a6:32:bf:54:13',
                    switch=None
                )

        ),
    }

    # bring up the network
    with WorkloadNetwork(hosts, ansible_ctx, ansible_quiet=False) as network:
        pass
