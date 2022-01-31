from __future__ import annotations

import json
import socket
import time
from contextlib import AbstractContextManager
from typing import Collection, Dict

import docker
from loguru import logger

from .hosts import LocalAinurHost, SDRWiFiNetwork, SoftwareDefinedRadio

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
                      sdr_wifi: SDRWiFiNetwork,
                      foreign_sta_macs: Collection[str]):

        logger.info(
            f'Starting SDR network with ssid: {sdr_wifi.ssid} on access '
            f'point {sdr_wifi.access_point}.')
        # make start network command dict
        sta_sdr_names_dict = {}
        for idx, sta_wifi in enumerate(sdr_wifi.stations):
            sta_sdr_names_dict['name_' + str(idx + 1)] = sta_wifi.name
        if len(sdr_wifi.stations) == 0:
            sta_sdr_names_dict = ''

        foreign_sta_macs_dict = {}
        for idx, mac in enumerate(foreign_sta_macs):
            foreign_sta_macs_dict['mac_' + str(idx + 1)] = mac
        if len(foreign_sta_macs) == 0:
            foreign_sta_macs_dict = ''

        start_sdrs_cmd = {
            'general'         : {
                'ssid'           : sdr_wifi.ssid,
                'channel'        : str(sdr_wifi.channel),
                'beacon_interval': sdr_wifi.beacon_interval,
                'ht_capable'     : sdr_wifi.ht_capable,
                'ap_sdr_name'    : sdr_wifi.access_point.name,
            },
            'sta_sdr_names'   : sta_sdr_names_dict,
            'foreign_sta_macs': foreign_sta_macs_dict,
        }

        self.send_command('start', start_sdrs_cmd)
        logger.info(f'SDR network with ssid: {sdr_wifi.ssid} is up.')

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
        received = str(self._socket.recv(3072), "utf-8")
        result_dict = json.loads(received)
        if result_dict['outcome'] == 'failed':
            logger.error(result_dict['content']['msg'])

    def create_wlans(self,
                     hosts: Dict[str, LocalAinurHost],
                     sdr_nets: Collection[SDRWiFiNetwork]):
        # Setup up the SDR network
        # find wlan_aps and create a wlan network per SDR AP
        # find sdr station wifis and foreign_sta_macs

        for sdr_net in sdr_nets:
            native_station_macs = []
            for host_name, host in hosts.items():
                for iface, config in host.wifis.items():
                    if config.ssid == sdr_net.ssid:
                        native_station_macs.append(config.mac)

            self.start_network(
                sdr_wifi=sdr_net,
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
