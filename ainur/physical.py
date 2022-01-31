from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Collection, Dict, Iterator, Mapping

from loguru import logger

from .ansible import AnsibleContext
from .hosts import AinurHost, SDRWiFiNetwork, Switch
from .managed_switch import ManagedSwitch
from .sdr_manager import SDRManager


class PhysicalLayer(AbstractContextManager, Mapping[str, AinurHost]):
    """
    Represents the physical layer connections of workload network

    Can be used as a context manager for easy deployment and automatic teardown
    of physical layer connections.
    """

    def __init__(self,
                 hosts: Dict[str, AinurHost],
                 sdr_nets: Collection[SDRWiFiNetwork],
                 switch: Switch,
                 ansible_context: AnsibleContext,
                 ansible_quiet: bool = True):
        """
        Parameters
        ----------
        """
        logger.info('Setting up physical layer.')

        # Instantiate network's switch
        self._switch = ManagedSwitch(name=switch.name,
                                     credentials=(switch.username,
                                                  switch.password),
                                     address=switch.management_ip,
                                     timeout=5,
                                     quiet=True)

        # Make workload switch vlans
        self._switch.make_connections(hosts=hosts)

        # Instantiate sdr network container
        radios = []
        for net in sdr_nets:
            radios.extend(net.radios)
        self._sdr_manager = SDRManager(
            sdrs=radios,
            docker_base_url='unix://var/run/docker.sock',
            container_image_name='sdr_manager:latest',
            sdr_config_addr='/opt/sdr-manager',
            use_jumbo_frames=False,
        )

        # Make workload wireless LANS
        self._sdr_manager.create_wlans(hosts=hosts, sdr_nets=sdr_nets)

        self._ansible_context = ansible_context
        self._quiet = ansible_quiet
        # self._inventory = inventory
        # self._network_desc = network_desc

        self._hosts = hosts

        logger.info('All connections are ready and double-checked.')

    def __len__(self) -> int:
        # return the number of hosts in the network
        return len(self._hosts)

    def __iter__(self) -> Iterator[str]:
        # return an iterator over the host names in the network.
        return iter(self._hosts.keys())

    def __getitem__(self, host_id: str) -> AinurHost:
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
