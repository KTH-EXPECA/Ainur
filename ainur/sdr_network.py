from __future__ import annotations

import docker
from docker.utils import create_host_config

from contextlib import AbstractContextManager
from ipaddress import IPv4Interface, IPv4Network
from typing import FrozenSet, Mapping
import json
import time

from loguru import logger
import socket
import sys

from .hosts import SoftwareDefinedRadio, SoftwareDefinedWiFiRadio


#DOCKER_BASE_URL='unix://var/run/docker.sock'
BEACON_INTERVAL = 100

class SDRNetwork(AbstractContextManager):
    """
    Represents a network of SDRs.

    Can be used as a context manager for easy sdr config container deployment
    and automatic teardown of it.
    """

    def __init__(self,
            sdrs: list[SoftwareDefinedRadio],
            docker_base_url: str,
            container_image_name: str,
            sdr_config_addr: str,
            use_jumbo_frames: bool = False,
            quiet: bool = True):
    

        self._sdrs = sdrs
        self._docker_base_url = docker_base_url
        self._container_image_name = container_image_name
        self._sdr_config_addr = sdr_config_addr
        self._use_jumbo_frames = use_jumbo_frames


        self._client = docker.APIClient(base_url=self._docker_base_url)
        volumes= [self._sdr_config_addr]
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
        #self._client.start(self._container)
        logger.info('sdr network container started.')

        time.sleep(1)

        # connect to the container server app
        # start the socket and connect
        HOST, PORT = "localhost", 50505
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(5)
        self._socket.connect((HOST, PORT))
        
        logger.info('socket connection to SDR network manager established.')

        # send nodes_ini 
        nodes_ini = {}
        for name,sdr in sdrs.items():
            nodes_ini[sdr.name] = { 'ip_address' : str(sdr.management_ip).split("/")[0] }

        init_dict = {
                        'nodes_ini' : nodes_ini,
                        'use_jumbo_frames' : self._use_jumbo_frames,
                        'management_network' : str(sdr.management_ip.network).split("/")[0]
                    }
        self.send_command('init',init_dict)
        logger.info('SDR network manager container is up.')

    def start_network(self,
            ap_wifi: SoftwareDefinedWiFiRadio,
            sta_wifis : List[SoftwareDefinedWiFiRadio],
            foreign_sta_macs : List[str],
            ):

        # make start network command dict
        sta_sdr_names_dict = {}
        for idx,sta_wifi in enumerate(sta_wifis):
            sta_sdr_names_dict['name_'+str(idx+1)] = sta_wifi.radio.name
        if len(sta_wifis) == 0:
            sta_sdr_names_dict = ''

        foreign_sta_macs_dict = {}
        for idx,mac in enumerate(foreign_sta_macs):
            foreign_sta_macs_dict['mac_'+str(idx+1)] = mac
        if len(foreign_sta_macs) == 0:
            foreign_sta_macs_dict = ''

        start_sdrs_cmd = {
            'general' : { 
                'ssid' : ap_wifi.ssid,
                'channel' : str(ap_wifi.channel),
                'beacon_interval' : str(BEACON_INTERVAL),
                'ap_sdr_name' : ap_wifi.radio.name,
            },
            'sta_sdr_names' : sta_sdr_names_dict,
            'foreign_sta_macs' : foreign_sta_macs_dict,
            'config' : ap_wifi.preset,
        }
       
        self.send_command('start',start_sdrs_cmd)
        logger.info('SDR network with ssid: %s is up.' % ap_wifi.ssid)

    def send_command(self,
            command_type: str,
            content: dict):

        cmd = {
            'command' : command_type,
            'content' : content,
        }

        msg = str(json.dumps(cmd))
        self._socket.sendall(bytes(msg + "\n", "utf-8"))

        # Receive response from the server
        received = str(self._socket.recv(3072), "utf-8")
        result_dict = json.loads(received)
        if result_dict['outcome'] == 'failed':
            logger.error(result_dict['content']['msg'])


    def tear_down(self) -> None:
        """
        Stop the SDR network config container.
        Note that after calling this method, this object will be left in an
        invalid state and should not be used any more.
        """
        logger.warning('Tearing down SDR network.')

        self.send_command('tear_down','')
        # close the socker
        self._socket.close()
        # stop the container
        self._client.stop(container=self._container, timeout=1)

        logger.warning('SDR network is stopped.')

    def __enter__(self) -> SDRNetwork:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(SDRNetwork, self).__exit__(exc_type, exc_val, exc_tb)
