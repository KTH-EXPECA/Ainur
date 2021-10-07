from __future__ import annotations

from contextlib import AbstractContextManager
from ipaddress import IPv4Interface, IPv4Network
from typing import FrozenSet, Mapping

import ansible_runner
from loguru import logger
import json

from .ansible import AnsibleContext
from .hosts import WorkloadHost,AnsibleHost,ConnectedWorkloadInterface,WorkloadInterface,Wire,SoftwareDefinedWiFiRadio,WiFiRadio,Phy,SwitchConnection
from .switch import ManagedSwitch

# TODO: needs testing


class WorkloadNetwork(AbstractContextManager):
    """
    Represents a connected workload network.

    Can be used as a context manager for easy deployment and automatic teardown
    of workload networks.
    """

    def __init__(self,
                 ip_hosts: Mapping[Tuple[IPv4Interface,Phy], WorkloadHost],
                 switch: ManagedSwitch,
                 sdrnetwork: SDRNetwork,
                 ansible_context: AnsibleContext,
                 ansible_quiet: bool = True):
        """
        Parameters
        ----------
        ip_hosts
            Mapping from desired IP addresses (given as IPv4 interfaces,
            i.e. addresses plus network masks) to hosts. Note that
            all given IP addresses must be in the same network segment.
        ansible_context:
            Ansible context to use.
        """
        logger.info('Setting up workload network.')

        # NOTE: mapping is ip -> host, and not host -> ip, since ip addresses
        # are unique in a network but a host may have more than one ip.

        # sanity check: all the addresses should be in the same subnet
        subnets = set([k[0].network for k in ip_hosts])
        if not len(subnets) == 1:
            raise RuntimeError(
                'Provided IPv4 interfaces should all belong to the '
                f'same network. Subnets: {subnets}')

        subnet = subnets.pop()
        logger.info(f'Workload network subnet: {subnet}')
        logger.info(f'Workload network hosts: {[k[0] for k in ip_hosts]}')

        self._ansible_context = ansible_context
        self._quiet = ansible_quiet

        # build an Ansible inventory
        self._inventory = {
            'all': {
                'hosts': {
                    host.ansible_host: {
                        'workload_interface': {
                            'type':host.workload_interface.type_name,
                            'name':host.workload_interface.name,
                            'ip':str(if_tup[0]),
                            'mac':host.workload_interface.mac_addr,
                            'switch': ('' if host.workload_interface.switch is None else {
                                'name':host.workload_interface.switch.name,
                                'port':host.workload_interface.switch.port,
                            }),
                        },
                        'workload_phy': ({
                            'type': if_tup[1].type_name,
                            'ssid': if_tup[1].ssid,
                            'preset' : if_tup[1].preset,
                            'mac': if_tup[1].radio.mac_addr,
                            'radio': if_tup[1].radio.name,
                        } if type(if_tup[1]) is SoftwareDefinedWiFiRadio else ({
                                'type': if_tup[1].type_name,
                                'ssid': if_tup[1].ssid,
                                'preset': if_tup[1].preset,
                        } if type(if_tup[1]) is WiFiRadio else {
                                'type': if_tup[1].type_name,
                        })),
                    } for if_tup, host in ip_hosts.items()
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

        
        # make network switch vlans
        for i, h in ip_hosts.items():
            ports = []
            if type(i[1])==SoftwareDefinedWiFiRadio:
                assert h.workload_interface.type_name == 'ethernets'
                ports.append(h.workload_interface.switch.port)
                ports.append(i[1].radio.switch.port)
                vlan_name = h.name+'_to_sdr_'+i[1].radio.name
            else:
                continue

            switch.make_vlan(ports=ports,name=vlan_name)

        # Setup up the SDR network
        # find wlan_ap
        # find sdr station wifis and foreign_sta_macs
        ap_wifi = None
        sta_wifis = []
        foreign_sta_macs = []
        for i, h in ip_hosts.items():
            if type(i[1])==SoftwareDefinedWiFiRadio:
                if i[1].type_name == 'SDR_AP':
                    ap_wifi = i[1]
                elif i[1].type_name == 'SDR_STA':
                    sta_wifis.append(i[1])
            elif type(i[1])==WiFiRadio:
                if i[1].type_name == 'NATIVE_STA':
                    foreign_sta_macs.append(h.workload_interface.mac_addr)

        print(foreign_sta_macs)
        if(ap_wifi is not None):
            sta_wifis = []
            foreign_sta_macs = ['00:e0:4c:35:53:25','00:e0:4c:37:a2:65']

            sdrnetwork.start_network(
                ap_wifi = ap_wifi,
                sta_wifis = sta_wifis,
                foreign_sta_macs = foreign_sta_macs,
            )


        # network is now up and running

        self._address = list(ip_hosts.keys())[0][0].network
        self._hosts = set(
            WorkloadHost(
                name=h.name,
                ansible_host=h.ansible_host,
                management_ip=h.management_ip,
                workload_interface= ConnectedWorkloadInterface( 
                    type_name=h.workload_interface.type_name,
                    name=h.workload_interface.name,
                    mac_addr=h.workload_interface.mac_addr,
                    switch=h.workload_interface.switch,
                    ip=i[0],
                    phy=i[1],
                )
            )
            for i, h in ip_hosts.items()
        )

    @property
    def hosts(self) -> FrozenSet[WorkloadHost]:
        return frozenset(self._hosts)

    @property
    def address(self) -> IPv4Network:
        return self._address

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

        self._address = None
        self._hosts.clear()
        logger.warning('Workload network has been torn down.')

    def __enter__(self) -> WorkloadNetwork:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(WorkloadNetwork, self).__exit__(exc_type, exc_val, exc_tb)

# TODO: need a way to test network locally
