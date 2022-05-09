from __future__ import annotations

import abc
from collections import defaultdict
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Interface
from typing import Any, Dict, Mapping, Tuple

import yaml
from dataclasses_json import config, dataclass_json


# Switch connection dataclass


# TODO: this file needs renaming. it's no longer only about hosts.
from frozendict import frozendict


@dataclass_json
@dataclass(frozen=True, eq=True)
class SwitchConnected(abc.ABC):
    switch_port: int


@dataclass_json
@dataclass(frozen=True, eq=True)
class Switch:
    name: str
    management_ip: IPv4Interface = field(
        metadata=config(encoder=str, decoder=IPv4Interface)
    )
    username: str
    password: str


@dataclass_json
@dataclass(frozen=True, eq=True)
class SoftwareDefinedRadio(SwitchConnected):
    name: str
    management_ip: IPv4Interface = field(
        metadata=config(encoder=str, decoder=IPv4Interface)
    )
    mac: str
    ssid: str
    net_name: str


@dataclass_json
@dataclass(frozen=True, eq=True)
class APSoftwareDefinedRadio(SoftwareDefinedRadio):
    channel: int
    beacon_interval: int
    ht_capable: bool


@dataclass_json
@dataclass(frozen=True, eq=True)
class StationSoftwareDefinedRadio(SoftwareDefinedRadio):
    pass


############
# Hosts Physical Layer Representation Classes
@dataclass_json
@dataclass(frozen=True, eq=True)
class WireSpec(SwitchConnected):
    net_name: str

    def get_switch_vlan_ports(self) -> Tuple[str, Tuple[int, ...]]:
        return self.net_name, (self.switch_port,)


@dataclass_json
@dataclass(frozen=True, eq=True)
class SwitchConfig:
    net_name: str
    port: int


@dataclass_json
@dataclass(frozen=True, eq=True)
class IPRoute:
    to: IPv4Interface = field(metadata=config(encoder=str, decoder=IPv4Interface))
    via: IPv4Address = field(metadata=config(encoder=str, decoder=IPv4Address))


@dataclass_json
@dataclass(frozen=True, eq=True)
class InterfaceCfg(abc.ABC):
    ip_address: IPv4Interface = field(
        metadata=config(encoder=str, decoder=IPv4Interface)
    )
    routes: Tuple[IPRoute, ...]
    mac: str

    @abc.abstractmethod
    def to_netplan_dict(self) -> Dict[str, Any]:
        """
        Converts this object to a valid Netplan interface dict.

        Returns
        -------
        dict

        """

        return {
            "addresses": [str(self.ip_address)],
            "dhcp4": False,
            "routes": [r.to_dict() for r in self.routes],
        }


@dataclass_json
@dataclass(frozen=True, eq=True)
class EthernetCfg(InterfaceCfg):
    wire_spec: WireSpec

    def to_netplan_dict(self) -> Dict[str, Any]:
        return super(EthernetCfg, self).to_netplan_dict()


@dataclass_json
@dataclass(frozen=True, eq=True)
class WiFiCfg(InterfaceCfg):
    ssid: str

    # TODO: implement non-open wifi config?

    def to_netplan_dict(self) -> Dict[str, Any]:
        cfg = super(WiFiCfg, self).to_netplan_dict()
        cfg["access-points"] = {self.ssid: {}}
        return cfg


@dataclass(eq=True)
class NetplanConfig:
    """
    Utility class to define a coherent Netplan config.
    """

    version: int = 2
    renderer: str = "networkd"
    configs: Dict[str, Dict[str, InterfaceCfg]] = field(
        default_factory=lambda: defaultdict(dict), init=False
    )

    def add_config(
        self, cfg_type: str, iface_name: str, config: InterfaceCfg
    ) -> NetplanConfig:
        self.configs[cfg_type][iface_name] = config
        return self

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
            "version": self.version,
            "renderer": self.renderer,
        }
        network_cfg.update(cfg_dicts)

        return {"network": network_cfg}

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


@dataclass_json
@dataclass(frozen=True, eq=True)
class ManagedHost:
    management_ip: IPv4Interface = field(
        metadata=config(encoder=str, decoder=IPv4Interface)
    )

    ansible_user: str


@dataclass_json
@dataclass(frozen=True, eq=True)
class AinurHost(ManagedHost, abc.ABC):
    @property
    @abc.abstractmethod
    def workload_ips(self) -> Tuple[IPv4Address]:
        pass


@dataclass_json
@dataclass(frozen=True, eq=True)
class LocalAinurHost(AinurHost):
    ethernets: frozendict[str, EthernetCfg]
    wifis: frozendict[str, WiFiCfg]

    def __post_init__(self):
        for iface, config in self.ethernets.items():
            if iface in self.wifis:
                raise HostError(
                    f"Duplicated interface {iface} definition in "
                    f"host {self.management_ip}."
                )

    @property
    def interfaces(self) -> Dict[str, InterfaceCfg]:
        ifaces = {}
        ifaces.update(self.ethernets)
        ifaces.update(self.wifis)
        return ifaces

    @property
    def interface_names(self) -> Tuple[str, ...]:
        return tuple(list(self.ethernets.keys()) + list(self.wifis.keys()))

    @property
    def ansible_host(self) -> str:
        return str(self.management_ip.ip)

    def gen_netplan_config(
        self, version: int = 2, renderer: str = "networkd"
    ) -> NetplanConfig:
        config = NetplanConfig(version=version, renderer=renderer)
        for name, interface in self.ethernets.items():
            config.add_config("ethernets", name, interface)

        for name, interface in self.wifis.items():
            config.add_config("wifis", name, interface)

        return config

    @property
    def workload_ips(self) -> Tuple[IPv4Address]:
        return tuple(
            [iface_cfg.ip_address.ip for iface_cfg in self.interfaces.values()]
        )


@dataclass_json
@dataclass(frozen=True, eq=True)
class AinurCloudHost(AinurHost):
    workload_ip: IPv4Interface = field(
        metadata=config(encoder=str, decoder=IPv4Interface)
    )

    public_ip: IPv4Address = field(metadata=config(encoder=str, decoder=IPv4Address))

    vpc_ip: IPv4Address = field(metadata=config(encoder=str, decoder=IPv4Address))

    @property
    def workload_ips(self) -> Tuple[IPv4Address]:
        return (self.workload_ip.ip,)  # NOTE THE COMMA


@dataclass_json
@dataclass(frozen=True, eq=True)
class AinurCloudHostConfig(AinurHost):
    workload_ip: IPv4Interface = field(
        metadata=config(encoder=str, decoder=IPv4Interface)
    )

    @property
    def workload_ips(self) -> Tuple[IPv4Address]:
        return (self.workload_ip.ip,)  # NOTE THE COMMA
