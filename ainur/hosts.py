from __future__ import annotations

import abc
from collections import defaultdict
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Interface
from typing import Any, Dict, FrozenSet, List, Literal, Optional, Tuple

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
class NetplanInterface:  # TODO: rename?
    # wraps everything we need to know about specific interfaces, like their
    # MAC address, netplan type, etc.
    netplan_type: Literal['ethernets', 'wifis']
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
class InterfaceCfg(abc.ABC):
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
            'addresses': [str(self.ip_address)],
            'dhcp4'    : False,
            'routes'   : [r.to_dict() for r in self.routes]
        }


@dataclass(frozen=True, eq=True)
class EthernetCfg(InterfaceCfg):
    def to_netplan_dict(self) -> Dict[str, Any]:
        return super(EthernetCfg, self).to_netplan_dict()


@dataclass(frozen=True, eq=True)
class WiFiCfg(InterfaceCfg):
    ssid: str

    # TODO: implement non-open wifi config?

    def to_netplan_dict(self) -> Dict[str, Any]:
        cfg = super(WiFiCfg, self).to_netplan_dict()
        cfg['access-points'] = {self.ssid: {}}
        return cfg


@dataclass(eq=True)
class NetplanConfig:
    """
    Utility class to define a coherent Netplan config.
    """

    version: int = 2
    renderer: str = 'networkd'
    configs: Dict[str, Dict[str, InterfaceCfg]] \
        = field(default_factory=lambda: defaultdict(dict), init=False)

    def _add_config(self,
                    cfg_type: str,
                    iface_name: str,
                    config: InterfaceCfg) -> NetplanConfig:
        self.configs[cfg_type][iface_name] = config
        return self

    @dispatch(str, EthernetCfg)
    def add_config(self, interface: str, config: InterfaceCfg) -> NetplanConfig:
        return self._add_config('ethernets', interface, config)

    @dispatch(str, WiFiCfg)
    def add_config(self, interface: str, config: InterfaceCfg) -> NetplanConfig:
        return self._add_config('wifis', interface, config)

    @dispatch(str, object)
    def add_config(self, interface: str, config: InterfaceCfg) -> NetplanConfig:
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
            for interface, cfg in configs.items():
                cfg_dicts[cfg_cat][interface] = cfg.to_netplan_dict()

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

    def __str__(self) -> str:
        return self.to_netplan_yaml()


class HostError(Exception):
    pass


class AinurHost:
    def __init__(self,
                 management_ip: IPv4Interface,
                 wkld_interfaces: Dict[str, NetplanInterface]):
        self._management_ip = management_ip
        self._interfaces: Dict[str, NetplanInterface] = dict(wkld_interfaces)
        self._configured_interfaces: Dict[str, InterfaceCfg] = dict()

    def __str__(self) -> str:
        return self.ansible_host

    @property
    def ansible_host(self) -> str:
        return str(self._management_ip.ip)

    @property
    def interfaces(self) -> Dict[str, NetplanInterface]:
        interfaces = {}
        interfaces.update(self._configured_interfaces)
        interfaces.update(self._interfaces)
        return interfaces

    def configure_interface(self,
                            name: str,
                            config: InterfaceCfg) -> None:
        if name not in self._configured_interfaces:
            if name in self._interfaces:
                self._configured_interfaces[name] = config
            else:
                raise HostError(f'No such interface {name} in host {self}.')
        else:
            raise HostError(f'Interface {name} is already configured.')

    def gen_netplan_config(self,
                           version: int = 2,
                           renderer: str = 'networkd') -> NetplanConfig:
        config = NetplanConfig(version=version, renderer=renderer)
        for name, interface in self._configured_interfaces:
            config.add_config(name, interface)

        return config

    @property
    def workload_ips(self) -> List[IPv4Address]:
        return [iface_cfg.ip_address.ip
                for iface_cfg in self._configured_interfaces.values()]
