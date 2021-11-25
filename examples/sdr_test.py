from ipaddress import IPv4Interface
from pathlib import Path
import json

from ainur import *


if __name__ == '__main__':

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
                ssid='ExpecaNetwork',
                channel=1,
                preset=str(json.dumps({ 
                    'use_jumbo_frames' : False,
                    'channel' : 6,
                    'beacon_interval' : 100,
                })),
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
    with SDRNetwork( 
                sdrs = radios,
                docker_base_url = 'unix://var/run/docker.sock',
                container_image_name = 'sdr_config:latest',
                sdr_config_addr = '/opt/sdr-config',
                use_jumbo_frames = False,
                quiet = False,
            ) as sdrnetwork:
        ap_wifi = SoftwareDefinedWiFiRadio(
                        type_name='SDR_AP',
                        ssid='Wlab_Test_Network',
                        channel=1,
                        preset='',
                        radio= radios['RFSOM-00002'],
        )
        sta_wifis = []
        foreign_sta_macs = ['00:e0:4c:35:53:25','00:e0:4c:37:a2:65'] 

        sdrnetwork.start_network(
            ap_wifi = ap_wifi,
            sta_wifis = sta_wifis,
            foreign_sta_macs = foreign_sta_macs,
        )

        input("Press Enter to continue...")

