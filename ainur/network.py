from __future__ import annotations

import json
from contextlib import AbstractContextManager
from typing import Any, Iterator, Mapping

import ansible_runner
from frozendict import frozendict
from loguru import logger

from .ansible import AnsibleContext
from .hosts import AinurHost
from .physical import PhysicalLayer


# TODO: needs testing

class Layer3Error(Exception):
    pass


class NetworkLayer(AbstractContextManager, Mapping[str, AinurHost]):
    """
    Represents a connected workload network.

    Can be used as a context manager for easy deployment and automatic teardown
    of workload networks.
    """

    # TODO: fix ugly networks parameter

    def __init__(self,
                 layer2: PhysicalLayer,
                 ansible_context: AnsibleContext,
                 ansible_quiet: bool = True):
        """
        Parameters
        ----------
        layer2:
            A PhysicalLayer object representing connected devices.
        ansible_context:
            Ansible context to use.
        ansible_quiet:
            Quiet Ansible output.
        """

        logger.info('Setting up layer 3 of the workload network.')

        host_info = '\n'.join([json.dumps({n: h.to_dict()},
                                          ensure_ascii=False,
                                          indent=2)
                               for n, h in layer2.items()])

        logger.debug(f'Layer 2 hosts:\n{host_info}')

        self._ansible_context = ansible_context
        self._quiet = ansible_quiet

        # build an Ansible inventory from the hosts
        self._inventory = {
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
            f'{json.dumps(self._inventory, indent=2, ensure_ascii=False)}'
        )

        # prepare a temp ansible environment and run the appropriate playbook
        with self._ansible_context(self._inventory) as tmp_dir:
            logger.info('Bringing up the network.')
            res = ansible_runner.run(
                playbook='net_up.yml',
                json_mode=False,
                private_data_dir=str(tmp_dir),
                quiet=self._quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'

            # network is now up and running

        self._hosts = frozendict(layer2)
        self._torn_down = False

    def __iter__(self) -> Iterator[str]:
        return iter(self._hosts)

    def __getitem__(self, item: str) -> AinurHost:
        return self._hosts[item]

    def __len__(self) -> int:
        return len(self._hosts)

    def __contains__(self, item: Any) -> bool:
        return item in self._hosts

    @property
    def is_down(self) -> bool:
        return self._torn_down

    @property
    def hosts(self) -> frozendict[str, AinurHost]:
        return self._hosts

    def tear_down(self) -> None:
        """
        Tears down this network.
        Note that after calling this method, this object will be left in an
        invalid state and should not be used any more.
        """

        if self._torn_down:
            return

        # prepare a temp ansible environment and run the appropriate playbook
        logger.warning('Tearing down workload network!')
        with self._ansible_context(self._inventory) as tmp_dir:
            res = ansible_runner.run(
                playbook='net_down.yml',
                json_mode=False,
                private_data_dir=str(tmp_dir),
                quiet=self._quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'
            # network is down

        self._torn_down = True
        logger.warning('Workload network has been torn down.')

    def __enter__(self) -> NetworkLayer:
        if self._torn_down:
            raise RuntimeError('Network has already been torn down.')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(NetworkLayer, self).__exit__(exc_type, exc_val,
                                                  exc_tb)

# TODO: need a way to test network locally
