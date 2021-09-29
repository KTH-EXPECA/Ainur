from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Host:
    name: str
    ansible_host: str


@dataclass(frozen=True)
class WorkloadHost(Host):
    workload_ip: str

    @classmethod
    def from_host(cls, host: Host) -> WorkloadHost:
        return WorkloadHost(**asdict(host))
