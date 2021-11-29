from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Interface
from typing import Dict, Literal

from dataclasses_json import config, dataclass_json


@dataclass_json
@dataclass(frozen=True, eq=True)
class NetplanInterface:
    # wraps everything we need to know about specific interfaces, like their
    # MAC address, netplan type, etc.

    # I decided to go with string literals instead of enums because you're
    # right, we probably won't need many more different types of netplan
    # configs, and this is easy to maintain.
    netplan_type: Literal['ethernets', 'wifis']
    mac: str
    # TODO: other things?


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
    # TODO: Samie
    workload_interface: str  # Points toward the workload interface to use in L3
    pass


@dataclass_json
@dataclass(frozen=True, eq=True)
class Layer3ConnectedWorkloadHost(Layer2ConnectedWorkloadHost):
    workload_ip: IPv4Interface = field(
        metadata=config(
            encoder=str,
            decoder=IPv4Interface
        )
    )

    def __str__(self) -> str:
        return f'{self.ansible_host} (management address ' \
               f'{self.management_ip}; workload address: {self.workload_ip})'
