from __future__ import annotations

from contextlib import AbstractContextManager
from operator import truediv
from typing import Dict, Iterator, Mapping

from loguru import logger

from .ansible import AnsibleContext
from .hosts import Layer2ConnectedWorkloadHost
from .managed_switch import ManagedSwitch
from .sdr_manager import SDRManager
from .fluent_server import FluentServer


class PhysicalLayer(AbstractContextManager,
                    Mapping[str, Layer2ConnectedWorkloadHost]):
    """
    Represents the physical layer connections of workload network

    Can be used as a context manager for easy deployment and automatic teardown
    of physical layer connections.
    """

    def __init__(self,
                 inventory: Dict,
                 network_desc: Dict,
                 ansible_context: AnsibleContext,
                 ansible_quiet: bool = True):
        """
        Parameters
        ----------
        """
        logger.info('Setting up physical layer.')

        # Instantiate network's switch
        self._switch = ManagedSwitch(name=inventory['switch'].name,
                                     credentials=(inventory['switch'].username,
                                                  inventory['switch'].password),
                                     address=inventory['switch'].management_ip,
                                     timeout=5,
                                     quiet=True)

        # Make workload switch vlans
        self._switch.make_connections(inventory=inventory,
                                      conn_specs=network_desc[
                                          'connection_specs'])

        # Instantiate Logger Module in Servre (Currently Galadriel)
        log_dirPath="./../Logs/" #Add path to log directory here, assuming it is situated in Ainur.
        self._fluent_server=FluentServer(log_dirPath)
        startFresh=True #Recreate and restart container, <ONLY for development phase>
        if startFresh==True:
            self._fluent_server.start_fresh
        else:
            elf._fluent_server.verify_status


        # Instantiate sdr network container
        self._sdr_manager = SDRManager(
            sdrs=inventory['radios'],
            docker_base_url='unix://var/run/docker.sock',
            container_image_name='sdr_manager:latest',
            sdr_config_addr='/opt/sdr-manager',
            use_jumbo_frames=False,
        )

        # Make workload wireless LANS
        self._sdr_manager.create_wlans(workload_hosts=inventory['hosts'],
                                       conn_specs=network_desc[
                                           'connection_specs'],
                                       networks=network_desc['subnetworks'])

        self._ansible_context = ansible_context
        self._quiet = ansible_quiet
        self._inventory = inventory
        self._network_desc = network_desc

        self._hosts = {
            host_name: Layer2ConnectedWorkloadHost(
                ansible_host=inventory['hosts'][host_name].ansible_host,
                management_ip=inventory['hosts'][host_name].management_ip,
                interfaces=inventory['hosts'][host_name].interfaces,
                phy=list(network_desc['connection_specs'][host_name].values())[
                    0].phy,
                workload_interface=
                list(network_desc['connection_specs'][host_name].keys())[0],
            ) for host_name in network_desc['connection_specs'].keys()
        }

        logger.info('All connections are ready and double-checked.')

    def __len__(self) -> int:
        # return the number of hosts in the network
        return len(self._hosts)

    def __iter__(self) -> Iterator[str]:
        # return an iterator over the host names in the network.
        return iter(self._hosts.keys())

    def __getitem__(self, host_id: str) -> Layer2ConnectedWorkloadHost:
        # implements the [] operator to look up Layer2 hosts by their
        # name.
        return self._hosts[host_id]

    def tear_down(self) -> None:
        """
        Tears down this network.
        Note that after calling this method, this object will be left in an
        invalid state and should not be used any more.
        """

        # prepare a temp ansible environment and run the appropriate playbook
        logger.warning('Tearing down physical layer!')

        self._switch.tear_down()
        self._sdr_manager.tear_down()
        self._hosts.clear()

        logger.warning('Physical layer has been torn down.')

    def __enter__(self) -> PhysicalLayer:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(PhysicalLayer, self).__exit__(exc_type, exc_val, exc_tb)
