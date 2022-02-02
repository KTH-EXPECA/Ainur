from __future__ import annotations

import json
from typing import Any, Iterator, Mapping

import ansible_runner
from frozendict import frozendict
from loguru import logger

from .common import Layer3Error, NetworkLayer
from ..ansible import AnsibleContext
from ..hosts import LocalAinurHost
from ..physical import PhysicalLayer


# TODO: needs testing


class LANLayer(NetworkLayer):
    """
    Represents a connected workload network.

    Can be used as a context manager for easy deployment and automatic teardown
    of workload networks.
    """

    # TODO: fix ugly networks parameter

    def __init__(self,
                 ansible_context: AnsibleContext,
                 ansible_quiet: bool = True):
        """
        ansible_context:
            Ansible context to use.
        ansible_quiet:
            Quiet Ansible output.
        """
        self._ansible_context = ansible_context
        self._ansible_quiet = ansible_quiet
        self._connected_hosts = {}

    def add_hosts(self, layer2: PhysicalLayer) -> LANLayer:
        """
        Parameters
        ----------
        layer2:
            A PhysicalLayer object representing connected devices.

        Returns
        -------
        self
            For chaining.
        """
        logger.info('Configuring layer 3 connections.')

        host_info = '\n'.join([json.dumps({n: h.to_dict()},
                                          ensure_ascii=False,
                                          indent=2)
                               for n, h in layer2.items()])

        logger.debug(f'Layer 2 hosts:\n{host_info}')

        # build an Ansible inventory from the hosts
        inventory = {
            'all': {
                'hosts': {
                    name: {
                        'ansible_host': host.ansible_host,
                        'netplan_cfg' : host
                            .gen_netplan_config()
                            .to_netplan_yaml(),
                        'interfaces'  : host.interface_names
                    }
                    for name, host in layer2.items()
                }
            }
        }

        logger.debug(
            'Configuring network layer with the following Ansible inventory:\n'
            f'{json.dumps(inventory, indent=2, ensure_ascii=False)}'
        )

        # prepare a temp ansible environment and run the appropriate playbook
        with self._ansible_context(inventory) as tmp_dir:
            logger.info('Bringing up the network.')
            res = ansible_runner.run(
                playbook='net_up.yml',
                json_mode=False,
                private_data_dir=str(tmp_dir),
                quiet=self._ansible_quiet,
            )

        if res.status == 'failed':
            logger.warning('Could not connect hosts on Layer3, aborting!')
            self._tear_down(layer2)
            raise Layer3Error('Could not establish Layer 3 connectivity.')

            # network is now up and running

        self._connected_hosts.update(layer2)
        return self

    def __iter__(self) -> Iterator[str]:
        return iter(self._connected_hosts)

    def __getitem__(self, item: str) -> LocalAinurHost:
        return self._connected_hosts[item]

    def __len__(self) -> int:
        return len(self._connected_hosts)

    def __contains__(self, item: Any) -> bool:
        return item in self._connected_hosts

    @property
    def hosts(self) -> frozendict[str, LocalAinurHost]:
        return frozendict(self._connected_hosts)

    def _tear_down(self, hosts: Mapping[str, LocalAinurHost]):
        # build an Ansible inventory from the hosts
        inventory = {
            'all': {
                'hosts': {
                    name: {
                        'ansible_host': host.ansible_host,
                        'netplan_cfg' : host
                            .gen_netplan_config()
                            .to_netplan_yaml(),
                        'interfaces'  : host.interface_names
                    }
                    for name, host in hosts.items()
                }
            }
        }

        with self._ansible_context(inventory) as tmp_dir:
            res = ansible_runner.run(
                playbook='net_down.yml',
                json_mode=False,
                private_data_dir=str(tmp_dir),
                quiet=self._ansible_quiet,
            )

        # TODO: better error checking
        if res.status == 'failed':
            raise Layer3Error('Encountered an error while tearing down Layer '
                              '3 connectivity.')
        # network is down

    def tear_down(self) -> None:
        """
        Tears down this network.
        """

        # prepare a temp ansible environment and run the appropriate playbook
        logger.warning('Tearing down Layer3 connectivity!')
        self._tear_down(self._connected_hosts)
        self._connected_hosts.clear()
        logger.warning('Layer 3 has been torn down.')

    def __enter__(self) -> LANLayer:
        return self

# TODO: need a way to test network locally
