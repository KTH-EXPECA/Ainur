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

import abc
import json
from dataclasses import dataclass, field
from ipaddress import IPv4Interface
from os import PathLike
from pathlib import Path
from typing import Any, Dict, Tuple, Type, Union

import yaml
from dataclasses_json import config, dataclass_json
from frozendict import frozendict


@dataclass_json
@dataclass(frozen=True, eq=True)
class _HasMACMixin(abc.ABC):
    mac: str

    def __post_init__(self):
        try:
            octets = self.mac.split(":")
            assert len(octets) == 6
            for octet in octets:
                # forcefully parse the octet
                int(f"0x{octet}", 16)
            # validated!
        except (ValueError, AssertionError):
            raise ValueError(f"{self.mac} is not a valid MAC address")


@dataclass_json
@dataclass(frozen=True, eq=True)
class ManagedResource(abc.ABC):
    management_ip: IPv4Interface = field(
        metadata=config(encoder=str, decoder=IPv4Interface)
    )


@dataclass_json
@dataclass(frozen=True, eq=True)
class _SwitchConnection:
    name: str
    port: int


@dataclass_json
@dataclass(frozen=True, eq=True)
class SwitchConnectedResource(abc.ABC):
    switch: _SwitchConnection


@dataclass_json
@dataclass(frozen=True, eq=True)
class SwitchResource(ManagedResource):
    username: str
    password: str
    ports: int
    reserved_ports: Tuple[int, ...]
    peers: frozendict[str, int]


@dataclass_json
@dataclass(frozen=True, eq=True)
class SDRResource(_HasMACMixin, ManagedResource, SwitchConnectedResource):
    pass


@dataclass_json
@dataclass(frozen=True, eq=True)
class _NIC(_HasMACMixin, abc.ABC):
    # default: bool
    pass


@dataclass_json
@dataclass(frozen=True, eq=True)
class _EthNIC(_NIC, SwitchConnectedResource):
    pass


@dataclass_json
@dataclass(frozen=True, eq=True)
class _WiFiNIC(_NIC):
    pass


@dataclass_json
@dataclass(frozen=True, eq=True)
class HostResource(ManagedResource, abc.ABC):
    ansible_user: str
    ethernets: frozendict[str, _EthNIC]
    wifis: frozendict[str, _WiFiNIC]

    def __post_init__(self):
        assert (len(self.ethernets) > 0) or (len(self.wifis) > 0)
        # TODO: default interfaces?


@dataclass_json
@dataclass(frozen=True, eq=True)
class WorkloadHostResource(HostResource):
    labels: frozendict[str, Any]


@dataclass_json
@dataclass(frozen=True, eq=True)
class GatewayResource(HostResource):
    to_networks: Tuple[IPv4Interface] = field(
        metadata=config(
            encoder=lambda t: json.dumps([str(e) for e in t]),
            decoder=lambda d: tuple([IPv4Interface(e) for e in d]),
        )
    )


@dataclass_json
@dataclass(frozen=True, eq=True)
class WiFiAPResource(SwitchConnectedResource):
    ssid: str
    metadata: frozendict[str, Any]


@dataclass_json
@dataclass(frozen=True, eq=True)
class ResourceCollection:
    switches: frozendict[str, SwitchResource]
    sdrs: frozendict[str, SDRResource]
    hosts: frozendict[str, WorkloadHostResource]
    gateways: frozendict[str, GatewayResource]
    wifi_aps: frozendict[str, WiFiAPResource]

    def __post_init__(self):
        if len(self.switches) == 0:
            raise ValueError("Need at least one switch.")
        elif len(self.hosts) == 0:
            raise ValueError("Need at least one host.")

        # check for name duplicates
        names = (
            set(self.switches.keys())
            .union(self.sdrs.keys())
            .union(self.hosts.keys())
            .union(self.gateways.keys())
            .union(self.wifi_aps.keys())
        )
        num_items = (
            len(self.switches)
            + len(self.sdrs)
            + len(self.hosts)
            + len(self.gateways)
            + len(self.wifi_aps)
        )

        if len(names) < num_items:
            raise ValueError("Duplicated names in testbed resource description.")

        # validate switch ports
        switch_ports: Dict[str, Dict[int, Tuple[str, str]]] = {
            name: {} for name, _ in self.switches.items()
        }

        def check_switch(
            resource_name: str,
            resource: Any,
            switch_cfg: _SwitchConnection,
        ):
            if switch_cfg.name not in self.switches:
                raise ValueError(
                    f"(Resource {resource_name} ({resource.__class__.__name__})) "
                    f"No such switch: '{switch_cfg.name}'."
                )
            elif switch_cfg.port > self.switches[switch_cfg.name].ports:
                raise ValueError(
                    f"(Resource {resource_name} ({resource.__class__.__name__})) "
                    f"Port {switch_cfg.port} outside switch {switch_cfg.name}'s "
                    f"range ({self.switches[switch_cfg.name].ports})."
                )
            elif switch_cfg.port in self.switches[switch_cfg.name].reserved_ports:
                raise ValueError(
                    f"(Resource {resource_name} ({resource.__class__.__name__})) "
                    f"Port {switch_cfg.port} is a reserved port on switch "
                    f"{switch_cfg.name}."
                )

            try:
                other_name, other_type = switch_ports[switch_cfg.name][switch_cfg.port]
                raise ValueError(
                    f"Port conflict on switch {switch_cfg.name}. "
                    f"Port {switch_cfg.port} claimed by both {resource_name} "
                    f"({resource.__class__.__name__}) and "
                    f"{other_name} ({other_type})"
                )
            except KeyError:
                switch_ports[switch_cfg.name][switch_cfg.port] = (
                    resource_name,
                    resource.__class__.__name__,
                )

        # SDRs
        for name, sdr in self.sdrs.items():
            check_switch(name, sdr, sdr.switch)

        # hosts/gateways
        for d in (self.hosts, self.gateways):
            for name, host in d.items():
                for nic_name, nic in host.ethernets.items():
                    check_switch(f"{name}.{nic_name}", host, nic.switch)

        # wifi aps
        for name, ap in self.wifi_aps.items():
            check_switch(name, ap, ap.switch)

    @classmethod
    def from_yaml(
        cls: Type[ResourceCollection],
        cfg_path: Union[PathLike, str],
    ) -> ResourceCollection:
        cfg_path = Path(cfg_path)

        with cfg_path.open("r") as fp:
            d = yaml.safe_load(fp)

        return cls.from_dict(d)


if __name__ == "__main__":
    print(ResourceCollection.from_yaml("../testbed-resources.yml"))
