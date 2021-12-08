from __future__ import annotations

import abc
import functools
import json
from contextlib import AbstractContextManager
from ipaddress import IPv4Interface, IPv4Network
from typing import Any, Collection, Iterator, Mapping

import ansible_runner
from frozendict import frozendict
from loguru import logger

from .ansible import AnsibleContext
from .hosts import Layer3ConnectedWorkloadHost, PhyNetwork
from .physical import PhysicalLayer


# TODO: needs testing

class Layer3Error(Exception):
    pass


class Layer3Network(AbstractContextManager,
                    Mapping[str, Layer3ConnectedWorkloadHost]):
    @abc.abstractmethod
    def __iter__(self) -> Iterator[str]:
        pass

    @abc.abstractmethod
    def __getitem__(self, item: str) -> Layer3ConnectedWorkloadHost:
        pass

    @abc.abstractmethod
    def __len__(self) -> int:
        pass

    @abc.abstractmethod
    def __contains__(self, item: Any) -> bool:
        pass

    @property
    @abc.abstractmethod
    def is_down(self) -> bool:
        pass

    @property
    @abc.abstractmethod
    def hosts(self) -> frozendict[str, Layer3ConnectedWorkloadHost]:
        pass

    @property
    @abc.abstractmethod
    def address(self) -> IPv4Network:
        pass

    @abc.abstractmethod
    def tear_down(self) -> None:
        pass

    def __enter__(self) -> Layer3Network:
        if self.is_down:
            raise RuntimeError('Network has already been torn down.')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(Layer3Network, self).__exit__(exc_type, exc_val, exc_tb)


class NetworkLayer(Layer3Network):
    """
    Represents a connected workload network.

    Can be used as a context manager for easy deployment and automatic teardown
    of workload networks.
    """

    # TODO: fix ugly networks parameter

    def __init__(self,
                 network_cfg: Mapping[str, PhyNetwork],
                 host_ips: Mapping[str, IPv4Interface],
                 layer2: PhysicalLayer,
                 ansible_context: AnsibleContext,
                 ansible_quiet: bool = True):
        """
        Parameters
        ----------
        network_cfg
            Name to PhyNetwork mapping.
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
        if not functools.reduce(lambda a, b: a if a == b else None, networks):
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
                workload_ip=ip,
                phy=layer2[name].phy,
                # FIXME: ugly getattr workaround. Use polymorphism and
                #  inheritance for this shit!!
                wifi_ssid=getattr(network_cfg[layer2[name].phy.network],
                                  'ssid', None)
            ) for name, ip in host_ips.items()
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


# TODO: need a way to test network locally


class VPNRouting(AbstractContextManager):
    def __init__(self,
                 base_network: NetworkLayer,
                 gateway_host: str,
                 remote_networks: Collection[IPv4Network],
                 ansible_ctx: AnsibleContext,
                 ansible_quiet: bool = True):
        # assumes VPN is set up

        self._network = base_network
        self._gw_host = gateway_host
        self._remote_nets = remote_networks
        self._ansible_ctx = ansible_ctx
        self._ansible_quiet = ansible_quiet

        # build the inventory
        workload_gw_ip = self._network[self._gw_host].workload_ip.ip
        management_gw_ip = self._network[self._gw_host].management_ip.ip

        self._inventory = {
            'all': {
                'children': {
                    'workload': {
                        'vars' : {
                            'gateway'    : str(workload_gw_ip),
                            'remote_nets': [str(net) for net in remote_networks]
                        },
                        'hosts': {
                            name: host.to_dict()
                            for name, host in self._network.items()
                            if name != self._gw_host
                        }
                    },
                    'management': {
                        'vars' : {
                            'gateway'    : str(management_gw_ip),
                            'remote_nets': [str(net) for net in remote_networks]
                        },
                        'hosts': {
                            'localhost': {
                                'ansible_connection': 'local'
                            }
                        }
                    }
                }
            }
        }

        logger.debug(
            f'Inventory for routing setup:\n{self._inventory}'
        )

    def __enter__(self) -> VPNRouting:
        logger.info(f'Setting up routing to the cloud through {self._gw_host}.')
        with self._ansible_ctx(self._inventory) as tmp_dir:
            res = ansible_runner.run(
                playbook='routing_up.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=self._ansible_quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'
            # routing is up

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.info('Tearing down routing to the cloud.')
        with self._ansible_ctx(self._inventory) as tmp_dir:
            res = ansible_runner.run(
                playbook='routing_down.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=self._ansible_quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'
            # routing is down


class CloudNetworkLayer(Layer3Network):
    def __init__(self,
                 network: Layer3Network,
                 cloud_hosts: Mapping[str, Layer3ConnectedWorkloadHost]):
        self._local_net = network
        self._cloud_hosts = frozendict(cloud_hosts)

    def __iter__(self) -> Iterator[str]:
        hosts = dict(self._local_net)
        hosts.update(self._cloud_hosts)
        return iter(hosts)

    def __getitem__(self, item: str) -> Layer3ConnectedWorkloadHost:
        try:
            return self._local_net[item]
        except KeyError:
            return self._cloud_hosts[item]

    def __len__(self) -> int:
        return len(self._local_net) + len(self._cloud_hosts)

    def __contains__(self, item: Any) -> bool:
        return item in self._local_net or item in self._cloud_hosts

    @property
    def is_down(self) -> bool:
        return self._local_net.is_down

    @property
    def hosts(self) -> frozendict[str, Layer3ConnectedWorkloadHost]:
        hosts = dict(self._local_net)
        hosts.update(self._cloud_hosts)
        return frozendict(hosts)

    @property
    def address(self) -> IPv4Network:
        return self._local_net.address

    def tear_down(self) -> None:
        pass
