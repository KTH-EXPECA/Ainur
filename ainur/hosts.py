from __future__ import annotations

import abc
from collections import defaultdict
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Interface
from typing import Any, Dict, FrozenSet, Literal, Optional, Set, \
    Tuple

import yaml
from dataclasses_json import config, dataclass_json
# Switch connection dataclass
from multipledispatch import dispatch


# TODO: this file needs renaming. it's no longer only about hosts.


@dataclass_json
@dataclass(frozen=True, eq=True)
class SwitchConnection:
    name: str
    port: int


@dataclass_json
@dataclass(frozen=True, eq=True)
class Switch:
    name: str
    management_ip: str
    username: str
    password: str


# SDR dataclass
@dataclass_json
@dataclass(frozen=True, eq=True)
class SoftwareDefinedRadio:
    name: str
    mac: str
    management_ip: IPv4Interface = field(
        metadata=config(
            encoder=str,
            decoder=IPv4Interface
        )
    )
    switch_connection: SwitchConnection


############
# Physical Layer Network Concept Representation Classes
@dataclass_json
@dataclass(frozen=True, eq=True)
class PhyNetwork:
    name: str


# WiFi network
@dataclass_json
@dataclass(frozen=True, eq=True)
class WiFiNetwork(PhyNetwork):
    ssid: str
    channel: int
    beacon_interval: int
    ht_capable: bool


# Wired network
@dataclass_json
@dataclass(frozen=True, eq=True)
class WiredNetwork(PhyNetwork):
    pass


############
# Hosts Physical Layer Representation Classes
@dataclass_json
@dataclass(frozen=True, eq=True)
class Phy:
    network: str  # corresponds to PhyNetwork name


@dataclass_json
@dataclass(frozen=True, eq=True)
class WiFi(Phy):
    is_ap: bool
    radio: str  # corresponds to SoftwareDefinedRadio or 'native'


@dataclass_json
@dataclass(frozen=True, eq=True)
class Wire(Phy):
    pass


############
# Workload Network Interface

@dataclass_json
@dataclass(frozen=True, eq=True)
class NetplanInterface:
    # wraps everything we need to know about specific interfaces, like their
    # MAC address, netplan type, etc.
    netplan_type: Literal['ethernets', 'wifis']
    name: str
    mac: str


@dataclass_json
@dataclass(frozen=True, eq=True)
class EthernetInterface(NetplanInterface):
    switch_connection: SwitchConnection
    netplan_type: Literal['ethernets'] = field(default='ethernets', init=False)


@dataclass_json
@dataclass(frozen=True, eq=True)
class WiFiInterface(NetplanInterface):
    netplan_type: Literal['wifis'] = field(default='wifis', init=False)


@dataclass_json
@dataclass(frozen=True, eq=True)
class ConnectionSpec:
    ip: IPv4Interface
    phy: Phy


############
# Workload Network Interface

@dataclass_json
@dataclass(frozen=True, eq=True)
class AnsibleHost:
    ansible_host: str


@dataclass_json
@dataclass(frozen=True, eq=True)
class WorkloadHost(AnsibleHost):
    management_ip: IPv4Interface = field(
        metadata=config(
            encoder=str,
            decoder=IPv4Interface
        )
    )

    # mapping of name -> interface
    interfaces: Dict[str, NetplanInterface]

    def __str__(self) -> str:
        return f'{self.ansible_host} (management address {self.management_ip})'


@dataclass_json
@dataclass(frozen=True, eq=True)
class Layer2ConnectedWorkloadHost(WorkloadHost):
    phy: Phy
    workload_interface: str  # Points toward the workload interface to use in L3


@dataclass_json
@dataclass(frozen=True, eq=True)
class Layer3ConnectedWorkloadHost(Layer2ConnectedWorkloadHost):
    workload_ip: IPv4Interface = field(
        metadata=config(
            encoder=str,
            decoder=IPv4Interface
        )
    )
    # TODO: fix?
    wifi_ssid: Optional[str] = field(default=None)

    def __str__(self) -> str:
        return f'{self.ansible_host} (management address ' \
               f'{self.management_ip}; workload address: {self.workload_ip})'


@dataclass_json
@dataclass(frozen=True, eq=True)
class IPRoute:
    to: IPv4Interface = field(
        metadata=config(
            encoder=str,
            decoder=IPv4Interface
        )
    )
    via: IPv4Address = field(
        metadata=config(
            encoder=str,
            decoder=IPv4Address
        )
    )


@dataclass(frozen=True, eq=True)
class _BaseNetplanIfaceCfg(abc.ABC):
    interface: str
    ip_address: IPv4Interface
    routes: Tuple[IPRoute] | FrozenSet[IPRoute]

    @abc.abstractmethod
    def to_netplan_dict(self) -> Dict[str, Any]:
        """
        Converts this object to a valid Netplan interface dict.

        Returns
        -------
        dict

        """

        return {
            self.interface: {
                'addresses': [str(self.ip_address)],
                'dhcp4'    : False,
                'routes'   : [r.to_dict() for r in self.routes]
            }
        }


@dataclass(frozen=True, eq=True)
class EthNetplanCfg(_BaseNetplanIfaceCfg):
    def to_netplan_dict(self) -> Dict[str, Any]:
        return super(EthNetplanCfg, self).to_netplan_dict()


@dataclass(frozen=True, eq=True)
class WiFiNetplanCfg(_BaseNetplanIfaceCfg):
    ssid: str

    # TODO: implement non-open wifi config?

    def to_netplan_dict(self) -> Dict[str, Any]:
        cfg = super(WiFiNetplanCfg, self).to_netplan_dict()
        cfg[self.interface]['access-points'] = {
            self.ssid: {
            }
        }
        return cfg


@dataclass(eq=True)
class NetplanConfig:
    """
    Utility class to define a coherent Netplan config.
    """

    version: int = 2
    renderer: str = 'networkd'
    configs: Dict[str, Set[_BaseNetplanIfaceCfg]] \
        = field(default_factory=lambda: defaultdict(set),
                init=False)

    def _add_config(self,
                    cfg_type: str,
                    config: _BaseNetplanIfaceCfg) -> None:
        self.configs[cfg_type].add(config)

    @dispatch(EthNetplanCfg)
    def add_config(self, config: _BaseNetplanIfaceCfg) -> None:
        return self._add_config('ethernets', config)

    @dispatch(WiFiNetplanCfg)
    def add_config(self, config: _BaseNetplanIfaceCfg) -> None:
        return self._add_config('wifis', config)

    @dispatch(object)
    def add_config(self, config: _BaseNetplanIfaceCfg) -> None:
        raise NotImplementedError(config)

    def to_netplan_dict(self):
        """
        Converts this object into a dictionary representing a valid Netplan
        config.

        Returns
        -------
        dict

        """
        cfg_dicts = defaultdict(dict)
        for cfg_cat, configs in self.configs.items():
            for netplan_cfg in configs:
                cfg_dicts[cfg_cat].update(netplan_cfg.to_netplan_dict())

        network_cfg = {
            'version' : self.version,
            'renderer': self.renderer,
        }
        network_cfg.update(cfg_dicts)

        return {'network': network_cfg}

    def to_netplan_yaml(self) -> str:
        """
        Converts this object into a string representation of a valid Netplan
        config.

        Returns
        -------
        str

        """
        return yaml.safe_dump(self.to_netplan_dict())
