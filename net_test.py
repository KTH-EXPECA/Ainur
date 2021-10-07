from ipaddress import IPv4Interface
from pathlib import Path
import json

from ainur import *


if __name__ == '__main__':
    # quick test to verify network + swarm work

    ansible_ctx = AnsibleContext(base_dir=Path('./ansible_env'))

    radios = {
        'RFSOM-00002': SoftwareDefinedRadio(
            name='RFSOM-00002',
            mac_addr='40:d8:55:04:2f:02',
            management_ip=IPv4Interface('192.168.1.61/24'),
            switch=SwitchConnection(name='glorfindel',port=40)
        ),
        'RFSOM-22222': SoftwareDefinedRadio(
            name='RFSOM-11111',
            mac_addr='02:05:f7:80:0b:72',
            management_ip=IPv4Interface('192.168.1.62/24'),
            switch=SwitchConnection(name='glorfindel',port=41)
        )
    }

    # build up a workload network
    hosts = {(
        IPv4Interface('10.0.0.7/24'),
            SoftwareDefinedWiFiRadio(
                type_name='SDR_AP',
                ssid='Wlan_New_Network',
                channel=1,
                preset='',
                radio= radios['RFSOM-00002'],
            )
        ) : WorkloadHost(
                name='cloudlet',
                ansible_host='workload-client-07',
                management_ip=IPv4Interface('192.168.1.107/24'),
                workload_interface=WorkloadInterface(
                    type_name='ethernets',
                    name='eth0',
                    mac_addr='dc:a6:32:bf:52:83',
                    switch=SwitchConnection(name='glorfindel',port=32)
                )
        ),(
        IPv4Interface('10.0.0.8/24'),
            WiFiRadio(
                type_name='NATIVE_STA',
                ssid='ExpecaNetwork',
                channel=1,
                preset=''
            )
        ) : WorkloadHost(
                name='endnode1',
                ansible_host='workload-client-08',
                management_ip=IPv4Interface('192.168.1.108/24'),
                workload_interface=WorkloadInterface(
                    type_name='wifis',
                    name='wlan1',
                    mac_addr='00:e0:4c:35:53:25',
                    switch=None
                )
        ),(
        IPv4Interface('10.0.0.9/24'),
            WiFiRadio(
                type_name='NATIVE_STA',
                ssid='ExpecaNetwork',
                channel=1,
                preset=''
            )
        ) : WorkloadHost(
                name='endnode2',
                ansible_host='workload-client-09',
                management_ip=IPv4Interface('192.168.1.109/24'),
                workload_interface=WorkloadInterface(
                    type_name='wifis',
                    name='wlan1',
                    mac_addr='00:e0:4c:37:a2:65',
                    switch=None
                )

        ),
    }

    # Instantiate sdr network container
    with SDRNetwork(
                    sdrs = radios,
                    docker_base_url = 'unix://var/run/docker.sock',
                    container_image_name = 'sdr_config:latest',
                    sdr_config_addr = '/opt/sdr-config',
                    use_jumbo_frames = False,
                    quiet = False ) as sdrnetwork:
        #Instantiante network's switch
        with ManagedSwitch('glorfindel', ('cisco','expeca'), IPv4Interface('192.168.1.5/24'), 5, quiet=True) as switch:
            # bring up the network
            with WorkloadNetwork(hosts, switch, sdrnetwork, ansible_ctx, ansible_quiet=False) as network:
                input("Press Enter to continue...")
