from __future__ import annotations

from contextlib import AbstractContextManager
from ipaddress import IPv4Interface, IPv4Network
from typing import FrozenSet, Mapping

import ansible_runner

from ainur.ansible import AnsibleContext
from ainur.hosts import ConnectedWorkloadHost, DisconnectedWorkloadHost


# TODO: needs testing


class WorkloadNetwork(AbstractContextManager):
    """
    Represents a connected workload network.

    Can be used as a context manager for easy deployment and automatic teardown
    of workload networks.
    """

    def __init__(self,
                 ip_hosts: Mapping[IPv4Interface, DisconnectedWorkloadHost],
                 ansible_context: AnsibleContext):
        """
        Parameters
        ----------
        ip_hosts
            Mapping from desired IP addresses (given as IPv4 interfaces,
            i.e. addresses plus network masks) to hosts. Note that
            all given IP addresses must be in the same network segment.
        ansible_context:
            Ansible context to use.
        """

        # NOTE: mapping is ip -> host, and not host -> ip, since ip addresses
        # are
        # unique in a network but a host may have more than one ip.

        # sanity check: all the addresses should be in the same subnet
        subnets = [k.network for k in ip_hosts]
        if not len(set(subnets)) == 1:
            raise RuntimeError(
                'Provided IPv4 interfaces should all belong to the '
                f'same network. Subnets: {subnets}')

        self._ansible_context = ansible_context

        # build an Ansible inventory
        self._inventory = {
            'all': {
                'hosts': {
                    host.name: {
                        'ansible_host': host.ansible_host,
                        'workload_nic': host.workload_nic,
                        'workload_ip' : str(interface)  # {ip}/{netmask}
                    } for interface, host in ip_hosts.items()
                }
            }
        }

        # prepare a temp ansible environment and run the appropriate playbook
        with self._ansible_context(self._inventory) as tmp_dir:
            res = ansible_runner.run(
                playbook='net_up.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=True,
            )

            # TODO: better error checking
            assert res.status != 'failed'

            # network is now up and running

        self._address = list(ip_hosts.keys())[0].network
        self._hosts = set(
            ConnectedWorkloadHost(
                name=h.name,
                ansible_host=h.ansible_host,
                workload_nic=h.workload_nic,
                workload_ip=i
            )
            for i, h in ip_hosts.items()
        )

    @property
    def hosts(self) -> FrozenSet[ConnectedWorkloadHost]:
        return frozenset(self._hosts)

    @property
    def address(self) -> IPv4Network:
        return self._address

    def tear_down(self) -> None:
        """
        Tears down this network.
        Note that after calling this method, this object will be left in an
        invalid state and should not be used any more.
        """

        # prepare a temp ansible environment and run the appropriate playbook
        with self._ansible_context(self._inventory) as tmp_dir:
            res = ansible_runner.run(
                playbook='net_down.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=True,
            )

            # TODO: better error checking
            assert res.status != 'failed'
            # network is down

        self._address = None
        self._hosts.clear()

    def __enter__(self) -> WorkloadNetwork:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(WorkloadNetwork, self).__exit__(exc_type, exc_val, exc_tb)

# TODO: need a way to test network locally
