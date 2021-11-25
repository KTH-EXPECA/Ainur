from __future__ import annotations

from contextlib import AbstractContextManager
from ipaddress import IPv4Interface, IPv4Network
from typing import FrozenSet, Mapping
from collections import defaultdict

import ansible_runner
from loguru import logger
import json

from .ansible import AnsibleContext
from .hosts import WorkloadHost,AnsibleHost,ConnectedWorkloadHost
from .hosts import WorkloadInterface,EthernetInterface,WiFiInterface
from .hosts import Wire,WiFi,Phy,SwitchConnection
from .managed_switch import ManagedSwitch

# TODO: needs testing


def get_interface_by_type(host: WorkloadHost, interface_type: WorkloadInterface):
    return [i for i in host.workload_interfaces if isinstance(i,interface_type) ][0]
    

class WorkloadNetwork(AbstractContextManager):
    """
    Represents a connected workload network.

    Can be used as a context manager for easy deployment and automatic teardown
    of workload networks.
    """

    def __init__(self,
                 ip_phy_hosts: list(Tuple[IPv4Interface,Phy,WorkloadHost]),
                 switch: ManagedSwitch,
                 sdr_network: SDRNetwork,
                 ansible_context: AnsibleContext,
                 ansible_quiet: bool = True):
        """
        Parameters
        ----------
        ip_hosts
            Mapping from desired IP addresses (given as IPv4 interfaces,`
            i.e. addresses plus network masks) to hosts. Note that
            all given IP addresses must be in the same network segment.
        ansible_context:
            Ansible context to use.
        """
        logger.info('Setting up workload network.')

        # NOTE: mapping is ip -> host, and not host -> ip, since ip addresses
        # are unique in a network but a host may have more than one ip.

        # sanity check: all the addresses should be in the same subnet
        subnets = set([k.network for k,p,h in ip_phy_hosts])
        for idx,subnet in enumerate(subnets):
            hosts = []
            for k,p,h in ip_phy_hosts:
                if k.network == subnet:
                    hosts.append(k)
            logger.info(f'Workload network #{idx} subnet: {subnet}, hosts: {hosts}')

        self._ansible_context = ansible_context
        self._quiet = ansible_quiet
        self._ip_phy_hosts = ip_phy_hosts

        # build an Ansible inventory
        self._inventory = {
            'all': {
                'hosts': {
                    host.ansible_host: {
                        'workload_interface': ({
                            'type': 'ethernets',
                            'name': get_interface_by_type(host,EthernetInterface).name,
                            'ip': str(ip),
                        } if isinstance(phy,WiFiSDR) or isinstance(phy,Wire) else ({
                            'type': 'wifis',
                            'ssid': phy.network.ssid,
                            'name': get_interface_by_type(host,WiFiInterface).name,
                            'ip': str(ip),
                        } if isinstance(phy,WiFiNative) else {
                        })),
                    } for ip, phy, host in ip_phy_hosts
                }
            }
        }

        # prepare a temp ansible environment and run the appropriate playbook
        with self._ansible_context(self._inventory) as tmp_dir:
            logger.info('Bringing up the network.')
            res = ansible_runner.run(
                playbook='net_up.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=self._quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'        

        
        # make workload switch vlans
        # WiFi sdr vlans
        for ip, phy, host in ip_phy_hosts:
            ports = []
            if isinstance(phy,WiFiSDR):
                host_port = get_interface_by_type(host,EthernetInterface).switch.port
                ports.append(host_port)
                ports.append(phy.radio.switch.port)
                vlan_name = host.ansible_host+'_to_'+phy.radio.name
            else:
                continue

            switch.make_vlan(ports=ports,name=vlan_name)

        # wired nodes vlans
        # connect the ones with the same network name
        ports_wired_nets = { 
            get_interface_by_type(host,EthernetInterface).switch.port : phy.network.name for ip, phy, host in ip_phy_hosts if isinstance(phy,Wire)
        }
        # Grouping dictionary by values and make lists of ports for each network name
        wired_nets = defaultdict(list)
        for key, value in sorted(ports_wired_nets.items()):
            wired_nets[value].append(key)

        for wired_net_name, ports_list in wired_nets.items():
            switch.make_vlan(ports=ports_list,name=wired_net_name)

        # TODO: find the wire physical layers and create vlans per subnet


        # Setup up the SDR network
        # find wlan_ap
        # find sdr station wifis and foreign_sta_macs
        for ip, phy, host in ip_phy_hosts:
            # a wlan network per AP
            if isinstance(phy,WiFiSDRAP):
                wifi_sdr_ap = phy
        
                sdr_stations = []
                native_stations_macs = []
            
                for ip_, phy_, host_ in ip_phy_hosts:
                    if isinstance(phy_,WiFiSDRSTA):
                        if phy_.network.ssid == wifi_sdr_ap.network.ssid :
                            sdr_stations.append(phy_)
                    elif isinstance(phy_,WiFiNativeSTA):
                        if phy_.network.ssid == wifi_sdr_ap.network.ssid :
                            native_phy_mac = get_interface_by_type(host_,WiFiInterface).mac_addr
                            native_stations_macs.append(native_phy_mac)
                
                # start a network
                sdr_network.start_network(
                    ap_wifi = wifi_sdr_ap,
                    sta_wifis = sdr_stations,
                    foreign_sta_macs = native_stations_macs,
                )

        # check the connections
        try:
            self.check_end2end()
        except AssertionError:
            self.tear_down()
            raise

        self._hosts = set(
            ConnectedWorkloadHost(
                ansible_host = host.ansible_host,
                management_ip = host.management_ip,
                ip= ip,
                phy= phy,
                workload_interface = get_interface_by_type(host,EthernetInterface) if (isinstance(phy,WiFiSDR) or isinstance(phy,Wire)) else get_interface_by_type(host,WiFiInterface)
            )
            for ip, phy, host in ip_phy_hosts
        )
        
    def check_end2end(self):

        # SDR networks
        # build an Ansible inventory
        # run the ansible playbook for the client hosts: not (isinstance(phy,WiFiSDRAP) or isinstance(phy,WiFiNativeAP) or isinstance(phy,Wire))
        # So they can ping the hosts behind the access points: (isinstance(phy_,WiFiSDRAP) or isinstance(phy_,WiFiNativeAP)) and they share the same subnet: (ip.network == ip_.network)
        inventory = {
            'all': {
                'hosts': {
                    host.ansible_host: { 
                        'targets': { 
                            'ip' : str(ip_).split("/")[0] for ip_, phy_, host_ in self._ip_phy_hosts if (isinstance(phy_,WiFiSDRAP) or isinstance(phy_,WiFiNativeAP)) and (ip.network == ip_.network)
                        }
                    } for ip, phy, host in self._ip_phy_hosts if not (isinstance(phy,WiFiSDRAP) or isinstance(phy,WiFiNativeAP) or isinstance(phy,Wire)) 
                }
            }
        }
            
        logger.info('Checking the workload network connections. All end-nodes must be able to ping their servers within 10 seconds.')
        for ip, phy, host in self._ip_phy_hosts: 
            if not (isinstance(phy,WiFiSDRAP) or isinstance(phy,WiFiNativeAP) or isinstance(phy,Wire)):
                for ip_, phy_, host_ in self._ip_phy_hosts:
                    if (isinstance(phy_,WiFiSDRAP) or isinstance(phy_,WiFiNativeAP)) and (ip.network == ip_.network):
                        logger.info(f'Ping check from {host.ansible_host} to {host_.ansible_host}')

        # prepare a temp ansible environment and run the appropriate playbook
        with self._ansible_context(inventory) as tmp_dir:
            res = ansible_runner.run(
                playbook='check_connection.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=True,
            )

            # TODO: better error checking
            assert res.status != 'failed'
                

        # Wired networks
        # build an Ansible inventory
        # run the ansible playbook for the client hosts: isinstance(phy,Wire)
        # So they can ping the hosts on the same subnet: isinstance(phy_,Wire) and they share the same subnet: (ip.network == ip_.network) and they are not the same host (host != host_)
        inventory = {
            'all': {
                'hosts': {
                    host.ansible_host: {
                        'targets': {
                            'ip' : str(ip_).split("/")[0] for ip_, phy_, host_ in self._ip_phy_hosts if isinstance(phy_,Wire) and (ip.network == ip_.network) and (host != host_)
                        }
                    } for ip, phy, host in self._ip_phy_hosts if isinstance(phy,Wire)
                }
            }
        }

        logger.info('Checking the workload network connections. All end-nodes must be able to ping their servers within 10 seconds.')
        for ip, phy, host in self._ip_phy_hosts:
            if isinstance(phy,Wire):
                for ip_, phy_, host_ in self._ip_phy_hosts:
                    if isinstance(phy_,Wire) and (ip.network == ip_.network) and (host != host_):
                        logger.info(f'Ping check from {host.ansible_host} to {host_.ansible_host}')

        # prepare a temp ansible environment and run the appropriate playbook
        with self._ansible_context(inventory) as tmp_dir:
            res = ansible_runner.run(
                playbook='check_connection.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=True,
            )

            # TODO: better error checking
            assert res.status != 'failed'

                        
        logger.info('All connections are ready and double-checked.')

    @property
    def hosts(self) -> FrozenSet[WorkloadHost]:
        return frozenset(self._hosts)

    def tear_down(self) -> None:
        """
        Tears down this network.
        Note that after calling this method, this object will be left in an
        invalid state and should not be used any more.
        """

        # prepare a temp ansible environment and run the appropriate playbook
        logger.warning('Tearing down workload network!')
        with self._ansible_context(self._inventory) as tmp_dir:
            res = ansible_runner.run(
                playbook='net_down.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=self._quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'
            # network is down

        self._hosts.clear()
        logger.warning('Workload network has been torn down.')

    def __enter__(self) -> WorkloadNetwork:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(WorkloadNetwork, self).__exit__(exc_type, exc_val, exc_tb)

# TODO: need a way to test network locally
