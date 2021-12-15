from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Dict, Iterator, Mapping

from loguru import logger

from .ansible import AnsibleContext
from .hosts import Layer2ConnectedWorkloadHost
from .managed_switch import ManagedSwitch
from .sdr_manager import SDRManager
from .radiohost_manager import RadioHostManager


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

        # save network's managed switch
        self._switch = inventory['switch']
        
        # Instantiate sdr manager
        self._sdr_manager = SDRManager(
            sdrs=inventory['radios'],
            docker_base_url='unix://var/run/docker.sock',
            container_image_name='sdr_manager:latest',
            sdr_config_addr='/opt/sdr-manager',
            use_jumbo_frames=False,
        )
        
        # Instantiate radio_host manager
        self._radiohost_manager = RadioHostManager(
            radiohosts=inventory['radiohosts'],
            ansible_context=ansible_context,
            ansible_quiet=ansible_quiet,
        )

        try:

            # Make workload switch vlans
            self._switch.make_connections(inventory=inventory,
                                          conn_specs=network_desc[
                                              'connection_specs'],
                                          radiohosts_config=network_desc[
                                              'radiohosts_config'],
                                          )

            # Make workload wireless LANS
            self._sdr_manager.create_wlans(workload_hosts=inventory['hosts'],
                                           conn_specs=network_desc[
                                               'connection_specs'],
                                           networks=network_desc['subnetworks'],
                                           )


            # Configure radio hosts for cellular networks
            self._radiohost_manager.config(conn_specs=network_desc['connection_specs'],
                                            configs=network_desc['radiohosts_config'],
                                            )

        except Exception as ex:        
            input("Caught an error, press Enter to tear down...")
            self.tear_down()
            raise ex

        else:

            self._ansible_context = ansible_context
            self._quiet = ansible_quiet
            self._inventory = inventory
            self._network_desc = network_desc

            # Implement RadioHosts Configurations
            # assign IPs
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

        self._sdr_manager.tear_down()
        self._radiohost_manager.tear_down()
        self._switch.tear_down()
        #self._hosts.clear()
        
        logger.warning('Physical layer has been torn down.')

    def __enter__(self) -> PhysicalLayer:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(PhysicalLayer, self).__exit__(exc_type, exc_val, exc_tb)
