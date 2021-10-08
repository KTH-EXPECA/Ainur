from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import IPv4Interface


@dataclass(frozen=True, eq=True)
class AnsibleHost:
    name: str
    ansible_host: str


@dataclass(frozen=True, eq=True)
class DisconnectedWorkloadHost(AnsibleHost):
    management_ip: IPv4Interface
    workload_nic: str


@dataclass(frozen=True, eq=True)
class ConnectedWorkloadHost(DisconnectedWorkloadHost):
    workload_ip: IPv4Interface
