from __future__ import annotations

import json
import socket
import time
from contextlib import AbstractContextManager
import docker
from loguru import logger
import functools
from ipaddress import IPv4Interface, IPv4Network
from typing import Any, Iterator, Mapping, Dict, List
from frozendict import frozendict

import ansible_runner
from .ansible import AnsibleContext

from .hosts import RadioHostConfig, WorkloadHost, LTE

class RadioHostManager(AbstractContextManager):
    """
    Represents a network of SDRs.

    Can be used as a context manager for easy sdr config container deployment
    and automatic teardown of it.
    """

    def __init__(self,
                 radiohosts: Dict[str, WorkloadHost],
                 ansible_context: AnsibleContext,
                 ansible_quiet: bool = True,
                 ):

        self._radiohosts = radiohosts
        self._ansible_context = ansible_context
        self._ansible_quiet = ansible_quiet

    def config(self,
                 configs: Dict[str, RadioHostConfig],
                 conn_specs,
                ):
        
        # make inventories 
        # 1. find enb and ue
        for host_name in conn_specs.keys():
            for if_name in conn_specs[host_name].keys():
                phy = conn_specs[host_name][if_name].phy
                # create a wlan network per SDR AP
                # TODO: isinstance check can be handled with inheritance and
                #  polymorphism.
                if isinstance(phy, LTE):
                    if phy.is_enb:
                        self._enb_radiohost_name = phy.radio_host
                    else:
                        self._ue_radiohost_name = phy.radio_host
        
        #print(self._enb_radiohost_name)
        #print(self._ue_radiohost_name)

        # build an Ansible inventory from the radio hosts
        self._radiohosts_inventory = {
            'all': {
                'hosts': {name: configs[name].to_dict() for name in
                          configs}
            }
        }
        # start ENB and EPC on ENB machine
        self._enb_inventory = {
            'all': {
                'hosts': {self._enb_radiohost_name: ""}
            }
        }
        
        # start UE on UE machines
        self._ue_inventory = {
            'all': {
                'hosts': {self._ue_radiohost_name: ""}
            }
        }
        
        #print(self._radiohosts_inventory)
        #print(self._enb_inventory)
        #print(self._ue_inventory)

        # network is now up and running
        self._torn_down = False
        
        # 2. setup the ips (should be done first)
        with self._ansible_context(self._radiohosts_inventory) as tmp_dir:
            logger.info('Setting radiohosts workload interfaces.')
            res = ansible_runner.run(
                playbook='radiohost_up.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=self._ansible_quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'

        # 3. start EPC+ENB
        with self._ansible_context(self._enb_inventory) as tmp_dir:
            logger.info('Bringing up EPC + ENB.')
            res = ansible_runner.run(
                playbook='enb_up.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=self._ansible_quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'

        # 4. start UE
        with self._ansible_context(self._ue_inventory) as tmp_dir:
            logger.info('Bringing up UE.')
            res = ansible_runner.run(
                playbook='ue_up.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                #quiet=self._ansible_quiet,
                quiet=False,
            )

            # TODO: better error checking
            assert res.status != 'failed'

        # 5. setup the routing
        # TODO


    @property
    def is_down(self) -> bool:
        return self._torn_down

    def tear_down(self) -> None:
        """
        Stop the SDR network config container.
        Note that after calling this method, this object will be left in an
        invalid state and should not be used any more.
        """
        logger.warning('Tearing down RadioHostManager.')

        if self._torn_down:
            return

        # prepare a temp ansible environment and run the appropriate playbook
        with self._ansible_context(self._ue_inventory) as tmp_dir:
            logger.warning('Tearing down UE.')
            res = ansible_runner.run(
                playbook='ue_down.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=self._ansible_quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'


        # prepare a temp ansible environment and run the appropriate playbook
        with self._ansible_context(self._enb_inventory) as tmp_dir:
            logger.warning('Tearing down EPC + ENB.')
            res = ansible_runner.run(
                playbook='enb_down.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=self._ansible_quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'


        # prepare a temp ansible environment and run the appropriate playbook
        logger.warning('Tearing down radiohosts workload interfaces!')
        with self._ansible_context(self._radiohosts_inventory) as tmp_dir:
            res = ansible_runner.run(
                playbook='radiohost_down.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=self._ansible_quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'
            # network is down

        self._torn_down = True

        logger.warning('RadioHosts are clean.')

    def __enter__(self) -> RadioHostManager:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(RadioHostManager, self).__exit__(exc_type, exc_val, exc_tb)
