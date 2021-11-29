from __future__ import annotations

import functools
import json
from contextlib import AbstractContextManager
from ipaddress import IPv4Interface, IPv4Network
from typing import Any, Iterator, Mapping, Tuple

import ansible_runner
from frozendict import frozendict
from loguru import logger

from .ansible import AnsibleContext
from .hosts import Layer3ConnectedWorkloadHost
from .physical import PhysicalLayer


# TODO: needs testing

class Layer3Error(Exception):
    pass


class NetworkLayer(AbstractContextManager,
                   Mapping[str, Layer3ConnectedWorkloadHost]):
    """
    Represents a connected workload network.

    Can be used as a context manager for easy deployment and automatic teardown
    of workload networks.
    """

    def __init__(self,
                 host_ips: Mapping[str, IPv4Interface],
                 layer2: PhysicalLayer,
                 ansible_context: AnsibleContext,
                 ansible_quiet: bool = True):
        """
        Parameters
        ----------
        host_ips
            Mapping from host ID to desired IP address.
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

        logger.info(f'Layer 2 hosts:\n{host_info}')

        # check that the given IP addresses all belong to the same network
        networks = list(map(lambda a: a.network, host_ips.values()))
        if not functools.reduce(lambda a, b: a == b, networks):
            raise Layer3Error('IPs provided do not all belong to same '
                              f'network.\n Inferred networks: {networks}.')

        logger.info(f'IP address mappings:\n{host_ips}')

        self._ansible_context = ansible_context
        self._quiet = ansible_quiet

        # build a collection of (future) connected workload hosts
        conn_hosts = frozendict({
            name: Layer3ConnectedWorkloadHost(
                ansible_host=layer2[name].ansible_host,
                management_ip=layer2[name].management_ip,
                interfaces=layer2[name].interfaces,
                workload_interface=layer2[name].workload_interface,
                workload_ip=ip
            ) for (name, ip), address in host_ips.items()
        })

        # build an Ansible inventory from the hosts
        self._inventory = {
            'all': {
                'hosts': {name: host.to_dict() for name, host in
                          conn_hosts.items()}
            }
        }

        # prepare a temp ansible environment and run the appropriate playbook
        with self._ansible_context(self._inventory) as tmp_dir:
            logger.info('Bringing up the network.')
            res = ansible_runner.run(
                playbook='net_up.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=self._quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'

            # network is now up and running

        self._network = networks[0]
        self._hosts = conn_hosts
        self._torn_down = False

    def __iter__(self) -> Iterator[str]:
        return iter(self._hosts)

    def __getitem__(self, item: str) -> Layer3ConnectedWorkloadHost:
        return self._hosts[item]

    def __len__(self) -> int:
        return len(self._hosts)

    def __contains__(self, item: Any) -> bool:
        return item in self._hosts

    @property
    def is_down(self) -> bool:
        return self._torn_down

    @property
    def hosts(self) -> frozendict[str, Layer3ConnectedWorkloadHost]:
        return self._hosts

    @property
    def address(self) -> IPv4Network:
        return self._network

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
                json_mode=True,
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
