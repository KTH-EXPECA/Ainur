from __future__ import annotations

import json
import socket
import time
from contextlib import AbstractContextManager
from typing import Dict, List

import docker
from loguru import logger

from .hosts import SoftwareDefinedRadio, WiFi, WiFiNetwork

# DOCKER_BASE_URL='unix://var/run/docker.sock'
BEACON_INTERVAL = 100


class SDRManager(AbstractContextManager):
    """
    Represents a network of SDRs.

    Can be used as a context manager for easy sdr config container deployment
    and automatic teardown of it.
    """

    def __init__(self,
                 sdrs: Dict[str, SoftwareDefinedRadio],
                 docker_base_url: str,
                 container_image_name: str,
                 sdr_config_addr: str,
                 use_jumbo_frames: bool = False):

        # need to have at least one sdr?
        if len(sdrs) < 1:
            raise RuntimeError('Must specify at least one SDR for SDRManager.')

        self._sdrs = sdrs
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
        for name, sdr in sdrs.items():
            nodes_ini[sdr.name] = {
                'ip_address': str(sdr.management_ip).split("/")[0]}

        # noinspection PyUnboundLocalVariable
        init_dict = {
            'nodes_ini'         : nodes_ini,
            'use_jumbo_frames'  : self._use_jumbo_frames,
            'management_network': str(sdr.management_ip.network).split("/")[0]
        }
        self.send_command('init', init_dict)
        logger.info('SDR network manager container is up.')

    def start_network(self,
                      ap_wifi: WiFi,
                      sta_wifis: List[WiFi],
                      foreign_sta_macs: List[str],
                      wifi_network: WiFiNetwork,
                      ):

        logger.info(
            f'Starting SDR network with ssid: {wifi_network.ssid} on access '
            f'point {ap_wifi.radio}.')
        # make start network command dict
        sta_sdr_names_dict = {}
        for idx, sta_wifi in enumerate(sta_wifis):
            sta_sdr_names_dict['name_' + str(idx + 1)] = sta_wifi.radio
        if len(sta_wifis) == 0:
            sta_sdr_names_dict = ''
        
        foreign_sta_macs_dict = {}
        for idx, mac in enumerate(foreign_sta_macs):
            foreign_sta_macs_dict['mac_' + str(idx + 1)] = mac
        if len(foreign_sta_macs) == 0:
            foreign_sta_macs_dict = ''

        start_sdrs_cmd = {
            'general'         : {
                'ssid'           : wifi_network.ssid,
                'channel'        : str(wifi_network.channel),
                'beacon_interval': wifi_network.beacon_interval,
                'ht_capable'     : wifi_network.ht_capable,
                'ap_sdr_name'    : ap_wifi.radio,
            },
            'sta_sdr_names'   : sta_sdr_names_dict,
            'foreign_sta_macs': foreign_sta_macs_dict,
        }
        
        self.send_command('start', start_sdrs_cmd)
        logger.info(f'SDR network with ssid: {wifi_network.ssid} is up.')

    def send_command(self,
                     command_type: str,
                     content: dict | str):

        cmd = {
            'command': command_type,
            'content': content,
        }

        msg = str(json.dumps(cmd))
        self._socket.sendall(bytes(msg + "\n", "utf-8"))

        # Receive response from the server
        received = str(self._socket.recv(3072), "utf-8")
        result_dict = json.loads(received)
        if result_dict['outcome'] == 'failed':
            logger.error(result_dict['content']['msg'])

    # noinspection PyMethodMayBeStatic
    def find_stations_of_ap(self, workload_hosts, conn_specs, wifi_sdr_ap):
        # find the wifi stations meant to be connected to the wifi_sdr_ap
        sdr_stations = []
        native_stations_macs = []
        # for host_name_ in conn_specs.keys():
        #     for if_name_ in conn_specs[host_name_].keys():
        #         phy_ = conn_specs[host_name_][if_name_].phy

        for host_name_, host in conn_specs.items():
            for if_name_, interface in host.items():
                phy_ = interface.phy

                # TODO: this if/elif does... nothing? Both the if and the
                #  elif check exactly the same condition. Also, we really
                #  should avoid isinstance checks, we can handle this
                #  behavior with inheritance and polymorphism.
                
                if isinstance(phy_, WiFi):
                    if (not phy_.is_ap):
                        if (phy_.radio != 'native'):
                            if phy_.network == wifi_sdr_ap.network:
                                sdr_stations.append(phy_)
                        else: #native
                            if phy_.network == wifi_sdr_ap.network:
                                native_phy_mac = \
                                    workload_hosts[host_name_].interfaces[if_name_].mac
                                native_stations_macs.append(native_phy_mac)

        return sdr_stations, native_stations_macs

    def create_wlans(self, workload_hosts, conn_specs, networks):
        # Setup up the SDR network
        # find wlan_aps and create a wlan network per SDR AP
        # find sdr station wifis and foreign_sta_macs
        for host_name in conn_specs.keys():
            for if_name in conn_specs[host_name].keys():
                phy = conn_specs[host_name][if_name].phy
                # create a wlan network per SDR AP
                # TODO: isinstance check can be handled with inheritance and
                #  polymorphism.
                if isinstance(phy, WiFi) \
                        and (phy.radio != 'native') and phy.is_ap:
                    wifi_sdr_ap = phy
                    sdr_stations, native_stations_macs = \
                        self.find_stations_of_ap(
                            workload_hosts=workload_hosts,
                            conn_specs=conn_specs, wifi_sdr_ap=wifi_sdr_ap)
                    # start a network
                    self.start_network(
                        ap_wifi=wifi_sdr_ap,
                        sta_wifis=sdr_stations,
                        foreign_sta_macs=native_stations_macs,
                        wifi_network=networks[phy.network],
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
