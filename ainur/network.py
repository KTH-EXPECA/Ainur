from __future__ import annotations

import json
from contextlib import AbstractContextManager
from ipaddress import IPv4Interface, IPv4Network
from typing import Any, Mapping, Tuple

import ansible_runner
from frozendict import frozendict
from loguru import logger

from .ansible import AnsibleContext
from .hosts import ConnectedWorkloadHost, DisconnectedWorkloadHost


# TODO: needs testing


class WorkloadNetwork(AbstractContextManager,
                      Mapping[str, ConnectedWorkloadHost]):
    """
    Represents a connected workload network.

    Can be used as a context manager for easy deployment and automatic teardown
    of workload networks.
    """

    def __init__(self,
                 cidr: IPv4Network | str,
                 hosts: Mapping[str, DisconnectedWorkloadHost],
                 ansible_context: AnsibleContext,
                 ansible_quiet: bool = True):
        """
        Parameters
        ----------
        cidr:
            IP address range for this network specified as a CIDR address block.
        hosts:
            A mapping from strings (representing unique identifiers) to
            hosts to add to the network.
        ansible_context:
            Ansible context to use.
        ansible_quiet:
            Quiet Ansible output.
        """

        # type coercion for the cidr block
        cidr = IPv4Network(cidr)

        logger.info('Setting up workload network.')
        logger.info(f'Workload network CIDR block: {cidr}')

        host_info = '\n'.join([json.dumps({n: h.to_dict()},
                                          ensure_ascii=False,
                                          indent=2)
                               for n, h in hosts.items()])

        logger.info(f'Workload network hosts: {host_info}')

        # check that all the hosts fit in the network prefix
        if len(hosts) > cidr.num_addresses - 2:  # exclude: network, broadcast
            raise RuntimeError('Not enough available addresses in CIDR block '
                               f'{cidr}. Required number of addresses = '
                               f'{len(hosts)}; available number of addresses '
                               f'= {cidr.num_addresses - 2}.')

        self._ansible_context = ansible_context
        self._quiet = ansible_quiet

        # build a collection of (future) connected workload hosts
        conn_hosts = frozendict({
            name: ConnectedWorkloadHost(
                ansible_host=host.ansible_host,
                workload_nic=host.workload_nic,
                workload_ip=IPv4Interface(f'{address}/{cidr.prefixlen}'),
                management_ip=host.management_ip
            ) for (name, host), address in zip(hosts.items(),
                                               cidr.hosts())
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

        self._network = cidr
        self._hosts = conn_hosts
        self._torn_down = False

    def __iter__(self) -> Tuple[str, ConnectedWorkloadHost]:
        for name_host in self._hosts.items():
            yield name_host

    def __getitem__(self, item: str) -> ConnectedWorkloadHost:
        return self._hosts[item]

    def __len__(self) -> int:
        return len(self._hosts)

    def __contains__(self, item: Any) -> bool:
        return item in self._hosts

    @property
    def is_down(self) -> bool:
        return self._torn_down

    @property
    def hosts(self) -> frozendict[str, ConnectedWorkloadHost]:
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

    def __enter__(self) -> WorkloadNetwork:
        if self._torn_down:
            raise RuntimeError('Network has already been torn down.')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(WorkloadNetwork, self).__exit__(exc_type, exc_val,
                                                     exc_tb)

# TODO: need a way to test network locally
