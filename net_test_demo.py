from ipaddress import IPv4Interface
from pathlib import Path
import json
import ansible_runner

from ainur import *


if __name__ == '__main__':
    # quick test to verify network + swarm work

    ansible_ctx = AnsibleContext(base_dir=Path('./ansible_env'))

    radios = {
        'RFSOM-00001': SoftwareDefinedRadio(
            name='RFSOM-00001',
            mac_addr='02:05:f7:80:0b:72',
            management_ip=IPv4Interface('192.168.1.61/24'),
            switch=SwitchConnection(name='glorfindel',port=41)
        ),
        'RFSOM-00002': SoftwareDefinedRadio(
            name='RFSOM-00002',
            mac_addr='02:05:f7:80:0b:19',
            management_ip=IPv4Interface('192.168.1.62/24'),
            switch=SwitchConnection(name='glorfindel',port=42)
        ),
        'RFSOM-00003': SoftwareDefinedRadio(
            name='RFSOM-00003',
            mac_addr='02:05:f7:80:02:c8',
            management_ip=IPv4Interface('192.168.1.63/24'),
            switch=SwitchConnection(name='glorfindel',port=43)
        ),
    }

    workload_hosts = {
        'workload-client-04' : WorkloadHost(
                ansible_host='workload-client-04',
                management_ip=IPv4Interface('192.168.1.104/24'),
                workload_interfaces = ( EthernetInterface(
                                            name='eth0',
                                            mac_addr='dc:a6:32:bf:53:b8',
                                            switch=SwitchConnection(name='glorfindel',port=29),
                                        ),
                ),
        ),
        'workload-client-05' : WorkloadHost(
                ansible_host='workload-client-05',
                management_ip=IPv4Interface('192.168.1.105/24'),
                workload_interfaces = ( EthernetInterface(
                                            name='eth0',
                                            mac_addr='dc:a6:32:07:fe:f2',
                                            switch=SwitchConnection(name='glorfindel',port=30),
                                        ),
                ),
        ),
        'workload-client-06' : WorkloadHost(
                ansible_host='workload-client-06',
                management_ip=IPv4Interface('192.168.1.106/24'),
                workload_interfaces = ( EthernetInterface(
                                            name='eth0',
                                            mac_addr='dc:a6:32:bf:53:f4',
                                            switch=SwitchConnection(name='glorfindel',port=31),
                                        ),
                ),
        ),
        'workload-client-07' : WorkloadHost(
                ansible_host='workload-client-07',
                management_ip=IPv4Interface('192.168.1.107/24'),
                workload_interfaces = ( EthernetInterface(
                                            name='eth0',
                                            mac_addr='dc:a6:32:bf:52:83',
                                            switch=SwitchConnection(name='glorfindel',port=32),
                                        ),
                ),
        ), 
        'workload-client-08' : WorkloadHost(
                ansible_host='workload-client-08',
                management_ip=IPv4Interface('192.168.1.108/24'),
                workload_interfaces = ( EthernetInterface(
                                            name='eth0',
                                            mac_addr='dc:a6:32:bf:54:12',
                                            switch=SwitchConnection(name='glorfindel',port=33),
                                        ),
                                        WiFiInterface(
                                            name='wlan0',
                                            mac_addr='f0:2f:74:63:5c:d9',
                                        ),
                ),
        ),
        'workload-client-09' : WorkloadHost(
                ansible_host='workload-client-09',
                management_ip=IPv4Interface('192.168.1.109/24'),
                workload_interfaces = ( EthernetInterface(
                                            name='eth0',
                                            mac_addr='dc:a6:32:bf:53:40',
                                            switch=SwitchConnection(name='glorfindel',port=34),
                                        ),
                ), 
        ),
    }

    
    # DEFINE WORKLOAD NETWORK
    # channels: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 36, 40, 44, 48]
    phy_networks = {
        'expeca_wlan_1' : WiFiNetwork(
            ssid = 'expeca_wlan_1',
            channel = 11,
            beacon_interval = 100,
            ht_capable = True,
        ),
        'wired_net_1' : WiredNetwork(
            name = 'wired_net_1',
        ),
    }

    # build up the workload networks
    # [(ip,phy,host),...]
    prebuilt_wl_network = [ ( 
            IPv4Interface('10.0.0.7/24'), 
            WiFiSDRAP(network = phy_networks['expeca_wlan_1'], radio=radios['RFSOM-00002']),
            workload_hosts['workload-client-07'],
        ),( IPv4Interface('10.0.0.8/24'),
            WiFiNativeSTA(network = phy_networks['expeca_wlan_1']),
            workload_hosts['workload-client-08'],
        ),( IPv4Interface('10.0.0.9/24'),
            WiFiSDRSTA(network = phy_networks['expeca_wlan_1'], radio=radios['RFSOM-00001']),
            workload_hosts['workload-client-09'],
        ),( IPv4Interface('10.0.1.4/24'),
            Wire(network = phy_networks['wired_net_1']),
            workload_hosts['workload-client-04'],
        ),( IPv4Interface('10.0.1.5/24'),
            Wire(network = phy_networks['wired_net_1']),
            workload_hosts['workload-client-05'],
        ),( IPv4Interface('10.0.1.6/24'),
            Wire(network = phy_networks['wired_net_1']),
            workload_hosts['workload-client-06'],
        )
    ]

    # Instantiate sdr network container
    with SDRNetwork(sdrs = radios,
                    docker_base_url = 'unix://var/run/docker.sock',
                    container_image_name = 'sdr_config:latest',
                    sdr_config_addr = '/opt/sdr-config',
                    use_jumbo_frames = False,
                    quiet = False ) as sdr_network:
        #Instantiante network's switch
        with ManagedSwitch(name='glorfindel', credentials=('cisco','expeca'), address=IPv4Interface('192.168.1.5/24'), timeout=5, quiet=True) as switch:
            # bring up the network
            with WorkloadNetwork(prebuilt_wl_network, switch, sdr_network, ansible_ctx, ansible_quiet=True) as wl_network:
                with TrafficControl(wl_network._hosts,ansible_ctx) as tc:
                    
                    inventory = {
                        'all': {
                            'hosts': {
                                'workload-client-04': {
                                    'type':'server',
                                    'workload_ip':'10.0.1.4'
                                },
                                'workload-client-05': {
                                    'type':'endnode',
                                    'target':'workload-client-04',
                                    'workload_ip':'10.0.1.5'
                                },
                                'workload-client-06': {
                                    'type':'endnode',
                                    'target':'workload-client-04',
                                    'workload_ip':'10.0.1.6'
                                },
                            }
                        }
                    }
                    # prepare a temp ansible environment and run the appropriate playbook
                    with ansible_ctx(inventory) as tmp_dir:
                        
                        res = ansible_runner.run(
                            playbook='irtt.yml',
                            json_mode=True,
                            private_data_dir=str(tmp_dir),
                            quiet=True,
                        )

                        for event in res.events:
                            if "task" in event["event_data"]:
                                if ( event["event_data"]["task"] == "report" ) and ( "res" in event["event_data"] ):
                                    print(event["event_data"]["res"]["msg"])

                    
                    tc.sample()
                    cli4_samples = [x for x in tc._traffic_info_samples if x.host == 'workload-client-04']
                    print(cli4_samples[1]-cli4_samples[0])

                    cli5_samples = [x for x in tc._traffic_info_samples if x.host == 'workload-client-05']
                    print(cli5_samples[1]-cli5_samples[0])
                    
                    cli6_samples = [x for x in tc._traffic_info_samples if x.host == 'workload-client-06']
                    print(cli6_samples[1]-cli6_samples[0])

                    input("Press Enter to continue...")
                

