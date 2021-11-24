from __future__ import annotations

from dataclasses import Field, dataclass, field
from ipaddress import IPv4Address, IPv4Interface
from typing import Type

from dataclasses_json import config, dataclass_json


def ip_field(cls: Type[IPv4Address], *args, **kwargs) -> Field:
    return field(
        *args,
        **kwargs,
        metadata=config(
            encoder=str,
            decoder=cls
        )
    )


@dataclass_json
@dataclass(frozen=True, eq=True)
class AnsibleHost:
    ansible_host: str


@dataclass_json
@dataclass(frozen=True, eq=True)
class DisconnectedWorkloadHost(AnsibleHost):
    workload_nic: str
    management_ip: IPv4Interface = ip_field(IPv4Interface)

    def __str__(self) -> str:
        return f'{self.ansible_host} (management address {self.management_ip})'


@dataclass_json
@dataclass(frozen=True, eq=True)
class ConnectedWorkloadHost(DisconnectedWorkloadHost):
    workload_ip: IPv4Interface = ip_field(IPv4Interface)

    def __str__(self) -> str:
        return f'{self.ansible_host} (management address ' \
               f'{self.management_ip}; workload address: {self.workload_ip})'
