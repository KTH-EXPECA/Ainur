from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address


@dataclass(frozen=True, eq=True)
class EC2Host:
    instance_id: str
    public_ip: IPv4Address
    vpc_ip: IPv4Address

    @property
    def public_vpn_host_string(self, vpn_port: int = 3210) -> str:
        return f'{self.public_ip}:{vpn_port}'

    @property
    def vpc_vpn_host_string(self, vpn_port: int = 3210) -> str:
        return f'{self.vpc_ip}:{vpn_port}'
