from __future__ import annotations

import json
import socket
import time
from contextlib import AbstractContextManager
from typing import Collection, Dict

import docker
from loguru import logger

from .hosts import APSoftwareDefinedRadio, LocalAinurHost, \
    SoftwareDefinedRadio, \
    StationSoftwareDefinedRadio

# DOCKER_BASE_URL='unix://var/run/docker.sock'
BEACON_INTERVAL = 100


class SDRManagerError(Exception):
    pass


class SDRManager(AbstractContextManager):
    """
    Represents a network of SDRs.

    Can be used as a context manager for easy sdr config container deployment
    and automatic teardown of it.
    """

    def __init__(self,
                 sdrs: Collection[SoftwareDefinedRadio],
                 docker_base_url: str,
                 container_image_name: str,
                 sdr_config_addr: str,
                 use_jumbo_frames: bool = False):

        # need to have at least one sdr?
        if len(sdrs) < 1:
            raise SDRManagerError('No SDRs specified.')

        # self._sdrs = sdrs
        self._docker_base_url = docker_base_url
        self._container_image_name = container_image_name
        self._sdr_config_addr = sdr_config_addr
        self._use_jumbo_frames = use_jumbo_frames

        self._client = docker.APIClient(base_url=self._docker_base_url)
        volumes = [self._sdr_config_addr]
        volume_bindings = {
            self._sdr_config_addr: {
                'bind': '/home/host',
                'mode': 'rw',
            },
        }

        host_config = self._client.create_host_config(
            binds=volume_bindings,
            network_mode='host',
        )

        self._container = self._client.create_container(
            image=self._container_image_name,
            volumes=volumes,
            host_config=host_config,
        )
        # start the container
        self._client.start(self._container)
        logger.info('sdr network container started.')

        time.sleep(1)

        # connect to the container server app
        # start the socket and connect
        host, port = "localhost", 50505
        # TODO: dont use magic numbers,
        #  put this in variables somewhere
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(5)
        self._socket.connect((host, port))

        logger.info('socket connection to SDR network manager established.')

        # send nodes_ini 
        nodes_ini = {}
        for sdr in sdrs:
            nodes_ini[sdr.name] = {
                'ip_address': str(sdr.management_ip.ip)
            }

        # noinspection PyUnboundLocalVariable
        init_dict = {
            'nodes_ini'         : nodes_ini,
            'use_jumbo_frames'  : self._use_jumbo_frames,
            'management_network': str(sdr.management_ip.network.network_address)
        }
        logger.debug('Initializing SDRs...')

        self.send_command('init', init_dict)
        logger.info('SDR network manager container is up.')

    def start_network(self,
                      sdr_ap: APSoftwareDefinedRadio,
                      sdr_stas: Collection[StationSoftwareDefinedRadio],
                      foreign_sta_macs: Collection[str]):

        logger.info(
            f'Starting SDR network with ssid: {sdr_ap.ssid} on access '
            f'point {sdr_ap.name}.')
        # make start network command dict

        if len(sdr_stas) > 0:
            sta_sdr_names_dict = {
                'name_' + str(idx + 1): station.name
                for idx, station in enumerate(sdr_stas)
            }
        else:
            sta_sdr_names_dict = ''

        if len(foreign_sta_macs) > 0:
            foreign_sta_macs_dict = {
                'mac_' + str(idx + 1): mac
                for idx, mac in enumerate(foreign_sta_macs)
            }
        else:
            foreign_sta_macs_dict = ''

        start_sdrs_cmd = {
            'general'         : {
                'ssid'           : sdr_ap.ssid,
                'channel'        : str(sdr_ap.channel),
                'beacon_interval': sdr_ap.beacon_interval,
                'ht_capable'     : sdr_ap.ht_capable,
                'ap_sdr_name'    : sdr_ap.name,
            },
            'sta_sdr_names'   : sta_sdr_names_dict,
            'foreign_sta_macs': foreign_sta_macs_dict,
        }

        self.send_command('start', start_sdrs_cmd)
        logger.info(f'SDR network with ssid: {sdr_ap.ssid} is up.')

    def send_command(self,
                     command_type: str,
                     content: dict | str):

        cmd = {
            'command': command_type,
            'content': content,
        }

        logger.debug(f'Sending command to SDR manager:\n{cmd}')
        self._socket.sendall(f'{json.dumps(cmd)}\n'.encode('utf8'))

        # Receive response from the server
        try:
            received = str(self._socket.recv(3072), "utf-8")
        except socket.error:
            logger.error('Encountered an error while contacting SDR manager.')
            raise

        result_dict = json.loads(received)
        if result_dict['outcome'] == 'failed':
            logger.error(result_dict['content']['msg'])
            raise SDRManagerError(result_dict['content']['msg'])

    def create_wlans(self,
                     hosts: Dict[str, LocalAinurHost],
                     sdr_aps: Collection[APSoftwareDefinedRadio],
                     sdr_stas: Collection[StationSoftwareDefinedRadio]):
        # Setup up the SDR network
        # find wlan_aps and create a wlan network per SDR AP
        # find sdr station wifis and foreign_sta_macs

        for ap_radio in sdr_aps:
            logger.info(f'Initializing SDR WiFi '
                        f'network on radio {ap_radio.name}.')
            logger.debug(f'Radio config: {ap_radio.to_json(indent=4)}')

            # find SDRs STAs connected to the AP ssid
            ap_stations = [
                sta_radio for sta_radio in sdr_stas
                if sta_radio.ssid == ap_radio.ssid
            ]

            # find native STAs connected to the AP ssid
            native_station_macs = []
            for host_name, host in hosts.items():
                for iface, config in host.wifis.items():
                    if config.ssid == ap_radio.ssid:
                        native_station_macs.append(config.mac)

            self.start_network(
                sdr_ap=ap_radio,
                sdr_stas=ap_stations,
                foreign_sta_macs=native_station_macs
            )

    def tear_down(self) -> None:
        """
        Stop the SDR network config container.
        Note that after calling this method, this object will be left in an
        invalid state and should not be used any more.
        """
        logger.warning('Tearing down SDR network.')

        self.send_command('tear_down', '')
        # close the socket
        self._socket.close()
        # stop the container
        self._client.stop(container=self._container, timeout=1)

        logger.warning('SDR network is stopped.')

    def __enter__(self) -> SDRManager:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(SDRManager, self).__exit__(exc_type, exc_val, exc_tb)
