from ipaddress import IPv4Interface
from pathlib import Path
import json

from ainur import *


if __name__ == '__main__':
    # quick test to verify network + swarm work

    ansible_ctx = AnsibleContext(base_dir=Path('./ansible_env'))

    radios = {
        'RFSOM-00003': SoftwareDefinedRadio(
            name='RFSOM-00003',
            mac_addr='02:05:f7:80:02:c8',
            management_ip=IPv4Interface('192.168.1.63/24'),
            switch=SwitchConnection(name='glorfindel',port=43)
        ),
        'RFSOM-00002': SoftwareDefinedRadio(
            name='RFSOM-00002',
            mac_addr='02:05:f7:80:0b:19',
            management_ip=IPv4Interface('192.168.1.62/24'),
            switch=SwitchConnection(name='glorfindel',port=42)
        ),
        'RFSOM-00001': SoftwareDefinedRadio(
            name='RFSOM-00001',
            mac_addr='02:05:f7:80:0b:72',
            management_ip=IPv4Interface('192.168.1.61/24'),
            switch=SwitchConnection(name='glorfindel',port=41)
        )
    }

    # [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 36, 40, 44, 48]
    wlan_ssid = 'Wlan_cots_11'
    wlan_channel = 11

    # build up a workload network
    hosts = {(
        IPv4Interface('10.0.0.7/24'),
            SoftwareDefinedWiFiRadio(
                type_name='SDR_AP',
                ssid=wlan_ssid,
                channel=wlan_channel,
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
                ssid=wlan_ssid,
                channel=wlan_channel,
                preset=''
            )
        ) : WorkloadHost(
                name='endnode-01',
                ansible_host='workload-client-08',
                management_ip=IPv4Interface('192.168.1.108/24'),
                workload_interface=WorkloadInterface(
                    type_name='wifis',
                    name='wlan0',
                    #mac_addr='00:e0:4c:35:53:25',
                    mac_addr='f0:2f:74:63:5c:d9',
                    switch=None
                )
        ),(
        IPv4Interface('10.0.0.9/24'),
            WiFiRadio(
                type_name='NATIVE_STA',
                ssid=wlan_ssid,
                channel=wlan_channel,
                preset=''
            )
        ) : WorkloadHost(
                name='endnode-02',
                ansible_host='workload-client-09',
                management_ip=IPv4Interface('192.168.1.109/24'),
                workload_interface=WorkloadInterface(
                    type_name='wifis',
                    name='wlan1',
                    #mac_addr='00:e0:4c:37:a2:65',
                    mac_addr='80:cc:9c:97:0b:6b',
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
            with WorkloadNetwork(hosts, switch, sdrnetwork, ansible_ctx, ansible_quiet=True) as network:
                input("Press Enter to continue...")


