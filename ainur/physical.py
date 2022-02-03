from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Collection, Dict, Iterator, List, Mapping

from loguru import logger

from .hosts import APSoftwareDefinedRadio, LocalAinurHost, \
    SoftwareDefinedRadio, StationSoftwareDefinedRadio, Switch
from .managed_switch import ManagedSwitch
from .sdr_manager import SDRManager, SDRManagerError


class PhyConfigError(Exception):
    pass


class PhysicalLayer(AbstractContextManager, Mapping[str, LocalAinurHost]):
    """
    Represents the physical layer connections of workload network

    Can be used as a context manager for easy deployment and automatic teardown
    of physical layer connections.
    """

    def __init__(self,
                 hosts: Dict[str, LocalAinurHost],
                 radio_aps: Collection[APSoftwareDefinedRadio],
                 radio_stas: Collection[StationSoftwareDefinedRadio],
                 switch: Switch):
        """
        Parameters
        ----------
        """

        # check that radio names are unique in aps and stas
        radio_names = set([r.name for r in radio_aps]) \
            .union([r.name for r in radio_aps])

        # TODO: need better way of checking radio uniqueness

        if len(radio_aps) + len(radio_stas) > len(radio_names):
            raise PhyConfigError('Repeated radio ids in AP and STA '
                                 'definitions!')

        radios: List[SoftwareDefinedRadio] = list(radio_aps)
        radios.extend(radio_stas)

        logger.info('Setting up physical layer.')
        # Instantiate network's switch
        self._switch = ManagedSwitch(name=switch.name,
                                     credentials=(switch.username,
                                                  switch.password),
                                     address=switch.management_ip,
                                     timeout=5)
        try:
            # Make workload switch vlans
            self._switch.make_connections(
                hosts=hosts,
                radios=radios
            )

            # Instantiate sdr network container
            try:
                self._sdr_manager = SDRManager(
                    sdrs=radios,
                    docker_base_url='unix://var/run/docker.sock',
                    container_image_name='sdr_manager:latest',
                    sdr_config_addr='/opt/sdr-manager',
                    use_jumbo_frames=False,
                )

                try:
                    # Make workload wireless LANS
                    self._sdr_manager.create_wlans(hosts=hosts,
                                                   sdr_aps=radio_aps,
                                                   sdr_stas=radio_stas)
                except Exception:
                    self._sdr_manager.tear_down()
                    raise

            except SDRManagerError:
                logger.warning('Skipping SDR initialization, no SDR networks '
                               'specified.')

                # this is to avoid null checks in tear down.
                # TODO: maybe fix?
                class DummySDRManager:
                    def tear_down(self) -> None:
                        pass

                self._sdr_manager = DummySDRManager()
            self._hosts = hosts

            logger.info('All connections are ready and double-checked.')
        except Exception:
            self._switch.tear_down()
            raise

    def __len__(self) -> int:
        # return the number of hosts in the network
        return len(self._hosts)

    def __iter__(self) -> Iterator[str]:
        # return an iterator over the host names in the network.
        return iter(self._hosts.keys())

    def __getitem__(self, host_id: str) -> LocalAinurHost:
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
