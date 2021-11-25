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
from .sdr_manager import SDRManager

# TODO: needs testing


def get_interface_by_type(host: WorkloadHost, interface_type: WorkloadInterface):
    return [i for i in host.workload_interfaces if isinstance(i,interface_type) ][0]
    

class PhyLayer(AbstractContextManager):
    """
    Represents the physical layer connections of workload network

    Can be used as a context manager for easy deployment and automatic teardown
    of physical layer connections.
    """

    def __init__(self,
                 inventory: dict,
                 network_desc: dict,
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

        # Instantiante network's switch
        self._switch = ManagedSwitch(name=inventory['switch'].name, 
                                     credentials=(inventory['switch'].username,inventory['switch'].password), 
                                     address=inventory['switch'].management_ip, 
                                     timeout=5, 
                                     quiet=True )

        # Make workload switch vlans
        self._switch.make_connections(inventory=inventory,conn_specs=network_desc['connection_specs'])


        # Instantiate sdr network container
        self._sdr_manager = SDRManager(sdrs = inventory['radios'],
                                       docker_base_url = 'unix://var/run/docker.sock',
                                       container_image_name = 'sdr_config:latest',
                                       sdr_config_addr = '/opt/sdr-config',
                                       use_jumbo_frames = False,
                                       quiet = False );

        # Make workload wireless LANS
        self._sdr_manager.create_wlans(workload_hosts=inventory['hosts'],
                                     conn_specs=network_desc['connection_specs'],
                                     networks=network_desc['subnetworks'])
        
        
        self._ansible_context = ansible_context
        self._quiet = ansible_quiet
        self._inventory = inventory
        self._network_desc = network_desc


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
        logger.warning('Tearing down phy!')

        self._switch.tear_down()
        self._sdr_manager.tear_down()

        logger.warning('Workload network has been torn down.')

    def __enter__(self) -> PhyLayer:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(PhyLayer, self).__exit__(exc_type, exc_val, exc_tb)

