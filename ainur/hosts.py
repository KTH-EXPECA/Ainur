from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import IPv4Interface

_ip_regex = re.compile('((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\\.|$)){4}')


@dataclass(frozen=True, eq=True)
class AnsibleHost:
    name: str
    ansible_host: str


@dataclass(frozen=True, eq=True)
class DisconnectedWorkloadHost(AnsibleHost):
    workload_nic: str


@dataclass(frozen=True, eq=True)
class ConnectedWorkloadHost(DisconnectedWorkloadHost):
    workload_ip: IPv4Interface
