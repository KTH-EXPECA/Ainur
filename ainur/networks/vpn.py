#  Copyright (c) 2022 KTH Royal Institute of Technology, Sweden,
#  and the ExPECA Research Group (PI: Prof. James Gross).
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from typing import Any, Collection, DefaultDict, Dict, Iterator, Set, \
    Tuple

import ansible_runner
import yaml
from loguru import logger
from mypy_boto3_ec2.type_defs import IpPermissionTypeDef, IpRangeTypeDef

from .common import Layer3Network
from ..ansible import AnsibleContext
from ..cloud.aws import CloudInstances, EC2Host
from ..hosts import AinurCloudHost, AinurCloudHostConfig


class VPNConfigError(Exception):
    pass


@dataclass(frozen=True, eq=True)
class _MeshConfig:
    ip: IPv4Interface
    psk: str
    port: int
    local_net: IPv4Network


@dataclass(frozen=True, eq=True)
class _Gateway:
    public_ip: IPv4Address
    mgmt_cfg: _MeshConfig
    wkld_cfg: _MeshConfig

    @property
    def mgmt_peer_addr(self) -> str:
        return f'{self.public_ip}:{self.mgmt_cfg.port}'

    @property
    def wkld_peer_addr(self) -> str:
        return f'{self.public_ip}:{self.wkld_cfg.port}'

    def gen_peer_configs(self, peer: IPv4Address) -> Tuple[str, str]:
        return (
            f'{peer}:{self.mgmt_cfg.port}',
            f'{peer}:{self.wkld_cfg.port}'
        )


@dataclass
class _VPNCloudHostCfg:
    ec2host: EC2Host
    ainur_config: AinurCloudHostConfig
    gateway: _Gateway
    mgmt_peers: Set[str] = field(init=False, default_factory=set)
    wkld_peers: Set[str] = field(init=False, default_factory=set)

    def __post_init__(self):
        self.mgmt_peers.add(self.gateway.mgmt_peer_addr)
        self.wkld_peers.add(self.gateway.wkld_peer_addr)

    def add_peer(self, peer: IPv4Address) -> None:
        mgmt_peer, wkld_peer = self.gateway.gen_peer_configs(peer)
        self.mgmt_peers.add(mgmt_peer)
        self.wkld_peers.add(wkld_peer)

    def to_ainur_host(self) -> AinurCloudHost:
        return AinurCloudHost(
            management_ip=self.ainur_config.management_ip,
            ansible_user=self.ainur_config.ansible_user,
            workload_ip=self.ainur_config.workload_ip,
            vpc_ip=self.ec2host.vpc_ip,
            public_ip=self.ec2host.public_ip
        )

    def dump_ansible_inventory(self) -> Dict[str, Any]:
        return {
            'ansible_host'                : str(self.ec2host.public_ip),
            'ansible_user'                : self.ainur_config.ansible_user,
            'ansible_ssh_private_key_file': self.ec2host.key_file,
            'vpn_configs'                 : {
                'management': {
                    'dev_name': 'vpn_mgmt',
                    'port'    : self.gateway.mgmt_cfg.port,
                    'peers'   : list(self.mgmt_peers),
                    'psk'     : self.gateway.mgmt_cfg.psk,
                    'ip'      : str(self.ainur_config.management_ip),
                    'gw_ip'   : str(self.gateway.mgmt_cfg.ip.ip),
                    'gw_net'  : str(self.gateway.mgmt_cfg.local_net)
                },
                'workload'  : {
                    'dev_name': 'vpn_wkld',
                    'port'    : self.gateway.wkld_cfg.port,
                    'peers'   : list(self.wkld_peers),
                    'psk'     : self.gateway.wkld_cfg.psk,
                    'ip'      : str(self.ainur_config.workload_ip),
                    'gw_ip'   : str(self.gateway.wkld_cfg.ip.ip),
                    'gw_net'  : str(self.gateway.wkld_cfg.local_net)
                }
            },
        }


class VPNCloudMesh(Layer3Network):
    def __init__(self,
                 gateway_ip: IPv4Address,
                 vpn_psk: str,
                 ansible_ctx: AnsibleContext,
                 ansible_quiet: bool = True,
                 gw_mgmt_ip: IPv4Interface = IPv4Interface('172.16.0.1/16'),
                 gw_wkld_ip: IPv4Interface = IPv4Interface('172.16.1.1/16'),
                 mgmt_local_net: IPv4Network = IPv4Network('192.168.0.0/16'),
                 wkld_local_net: IPv4Network = IPv4Network('10.0.0.0/16'),
                 mgmt_port: int = 3210,
                 wkld_port: int = 3211, ):
        """
        Parameters
        ----------
        gateway_ip
            Public IP address of the local gateway.
        vpn_psk
            Pre-shared key used by VPNCloud to establish a connection.
        gw_mgmt_ip
            IP address of the gateway in the management VPN network.
        gw_wkld_ip
            IP address of the gateway in the workload VPN network.
        mgmt_local_net
            The local management network. Used to set up routes.
        wkld_local_net
            The local workload network. Used to set up routes.
        mgmt_port
            The management network VPNCloud UDP port.
        wkld_port
            The workload network VPNCloud UDP port.
        ansible_ctx
            Ansible context to use.
        ansible_quiet
            Quiet ansible output.
        """

        self._gateway = _Gateway(
            public_ip=gateway_ip,
            mgmt_cfg=_MeshConfig(
                ip=gw_mgmt_ip,
                psk=vpn_psk,
                port=mgmt_port,
                local_net=mgmt_local_net
            ),
            wkld_cfg=_MeshConfig(
                ip=gw_wkld_ip,
                psk=vpn_psk,
                port=wkld_port,
                local_net=wkld_local_net
            )
        )

        # dictionary of {keys: {hosts: hostcfgs}}
        self._conn_hosts: DefaultDict[str, Dict[str, _VPNCloudHostCfg]] = \
            defaultdict(dict)

        # keep track of individual instance ids to prevent clashes
        self._host_ids = set()

        self._ansible_ctx = ansible_ctx
        self._ansible_quiet = ansible_quiet

    def connect_cloud(self,
                      cloud_layer: CloudInstances,
                      host_configs: Collection[AinurCloudHostConfig]):
        """

        Parameters
        ----------
        cloud_layer
            Cloud instances to connect to the testbed via VPNCloud.
        host_configs
            VPN IP configurations for the cloud hosts. Length must match the
            number of cloud instances in the cloud layer.

        Returns
        -------
        self
            For chaining and usage as a context manager.
        """

        if (lcloud := len(cloud_layer)) != (lcfg := len(host_configs)):
            raise VPNConfigError(f'Number of cloud host configs ({lcfg})'
                                 'does not match the number of available '
                                 f'cloud instances ({lcloud}).')

        logger.info(f'Connecting {cloud_layer} to VPN mesh.')

        # pair cloud instances with configs
        cloud_hosts = {}
        for (iid1, ec2host1), config1 in zip(cloud_layer.items(), host_configs):
            if iid1 in self._host_ids:
                raise VPNConfigError('Attempting to configure VPN mesh on '
                                     'already-configured instance.')

            peer1 = _VPNCloudHostCfg(
                ec2host=ec2host1,
                ainur_config=config1,
                gateway=self._gateway
            )

            # regional peers
            for (iid2, ec2host2), config2 in zip(cloud_layer.items(),
                                                 host_configs):
                if iid1 != iid2:  # peers dont connect to themselves
                    self._check_ip_assignments(peer1.ainur_config, config2)
                    peer1.add_peer(ec2host2.vpc_ip)

            # non-regional peers
            for other_host_group in self._conn_hosts.values():
                for host in other_host_group.values():
                    self._check_ip_assignments(peer1.ainur_config,
                                               host.ainur_config)
                    peer1.add_peer(host.ec2host.public_ip)

            cloud_hosts[iid1] = peer1

        # attach security groups
        cloud_layer.create_sec_group(
            name='expecavpn',
            desc='Ephemeral SecGroup for VPN and SSH access.',
            attach_to_instances=True,
            ephemeral=True,
            ingress_rules=[
                # rules allowing inbound traffic from mgmt vpn
                IpPermissionTypeDef(
                    IpRanges=[
                        IpRangeTypeDef(
                            CidrIp='0.0.0.0/0', Description='Everywhere'
                        ),
                    ],
                    FromPort=self._gateway.mgmt_cfg.port,
                    ToPort=self._gateway.mgmt_cfg.port,
                    IpProtocol='tcp'
                ),
                IpPermissionTypeDef(
                    IpRanges=[
                        IpRangeTypeDef(
                            CidrIp='0.0.0.0/0', Description='Everywhere'
                        ),
                    ],
                    FromPort=self._gateway.mgmt_cfg.port,
                    ToPort=self._gateway.mgmt_cfg.port,
                    IpProtocol='udp'
                ),
                # rules allowing inbound traffic from wkld vpn
                IpPermissionTypeDef(
                    IpRanges=[
                        IpRangeTypeDef(
                            CidrIp='0.0.0.0/0', Description='Everywhere'
                        ),
                    ],
                    FromPort=self._gateway.wkld_cfg.port,
                    ToPort=self._gateway.wkld_cfg.port,
                    IpProtocol='tcp'
                ),
                IpPermissionTypeDef(
                    IpRanges=[
                        IpRangeTypeDef(
                            CidrIp='0.0.0.0/0', Description='Everywhere'
                        ),
                    ],
                    FromPort=self._gateway.wkld_cfg.port,
                    ToPort=self._gateway.wkld_cfg.port,
                    IpProtocol='udp'
                ),
            ]
        )

        # prepare the ansible inventory to configure the cloud instances
        keyfile = cloud_layer.keyfile
        # noinspection DuplicatedCode
        inventory = {
            'all': {
                'hosts': {
                    host_id: host_cfg.dump_ansible_inventory()
                    for host_id, host_cfg in cloud_hosts.items()
                }
            }
        }

        logger.debug(f'Using inventory:\n{yaml.safe_dump(inventory)}')
        logger.debug(f'Using private key {keyfile}.')

        # deploy
        with self._ansible_ctx(
                inventory=inventory,
                ssh_key=keyfile
        ) as tmp_dir:
            res = ansible_runner.run(
                playbook='vpncloud_up.yml',
                json_mode=False,
                private_data_dir=str(tmp_dir),
                quiet=self._ansible_quiet
            )

        if res.status == 'failed':
            logger.warning(f'Failed to bring up VPN mesh on {cloud_layer}!')
            logger.warning('Attempting to clean up.')
            self._tear_down_vpn(keyfile, cloud_hosts)
            raise VPNConfigError(f'Failed to bring up '
                                 f'VPN mesh on {cloud_layer}!')

        logger.warning(f'VPN mesh on {cloud_layer} deployed.')

        # update the host list
        self._conn_hosts[keyfile].update(cloud_hosts)
        self._host_ids.update(cloud_hosts.keys())
        return self

    @staticmethod
    def _check_ip_assignments(peer1: AinurCloudHostConfig,
                              peer2: AinurCloudHostConfig) -> None:
        try:
            assert peer1.management_ip.ip != peer2.management_ip.ip
            assert peer1.workload_ip.ip != peer2.workload_ip.ip
        except AssertionError:
            raise VPNConfigError('Clashing IP address configurations for '
                                 f'{peer1} and {peer2}.')

        # TODO: check networks?

    def _tear_down_vpn(self,
                       keyfile: str,
                       hosts: Dict[str, _VPNCloudHostCfg]) -> None:
        # noinspection DuplicatedCode
        inventory = {
            'all': {
                'hosts': {
                    host_id: host_cfg.dump_ansible_inventory()
                    for host_id, host_cfg in hosts.items()
                }
            }
        }
        logger.debug(f'Using inventory:\n{yaml.safe_dump(inventory)}')
        logger.debug(f'Keyfile: {keyfile}')
        logger.warning('Tearing down VPN connections...')
        with self._ansible_ctx(inventory=inventory,
                               ssh_key=keyfile) as tmp_dir:
            ansible_runner.run(
                playbook='vpncloud_down.yml',
                json_mode=False,
                private_data_dir=str(tmp_dir),
                quiet=self._ansible_quiet
            )

    def tear_down(self) -> None:
        for keyfile, hostgroup in self._conn_hosts.items():
            self._tear_down_vpn(keyfile, hostgroup)
        self._conn_hosts.clear()
        self._host_ids.clear()
        logger.warning('VPN mesh layer torn down.')

    def __enter__(self) -> VPNCloudMesh:
        return self

    def __iter__(self) -> Iterator[str]:
        return iter(self._host_ids)

    def __getitem__(self, item: str) -> AinurCloudHost:
        if item in self._host_ids:
            for _, hostgroup in self._conn_hosts.items():
                try:
                    return hostgroup[item].to_ainur_host()
                except KeyError:
                    continue

        raise KeyError(item)

    def __len__(self) -> int:
        return len(self._host_ids)

    def __contains__(self, item: Any) -> bool:
        return item in self._host_ids
