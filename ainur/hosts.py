from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import IPv4Interface

_ip_regex = re.compile('((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\\.|$)){4}')

@dataclass(frozen=True, eq=True)
class SwitchConnection:
    name: str
    port: int

@dataclass(frozen=True, eq=True)
class Phy:
    type_name: str

@dataclass(frozen=True, eq=True)
class WiFiRadio(Phy):
    ssid: str
    channel: int
    preset: str

@dataclass(frozen=True, eq=True)
class SoftwareDefinedWiFiRadio(WiFiRadio):
    radio: SoftwareDefinedRadio 
    
@dataclass(frozen=True, eq=True)
class Wire(Phy):
    switch: SwitchConnection

@dataclass(frozen=True, eq=True)
class WorkloadInterface:
    type_name: str
    name: str
    mac_addr: str
    switch: SwitchConnection

@dataclass(frozen=True, eq=True)
class ConnectedWorkloadInterface(WorkloadInterface):
    phy: Phy
    ip: IPv4Interface

@dataclass(frozen=True, eq=True)
class AnsibleHost:
    name: str
    ansible_host: str

@dataclass(frozen=True, eq=True)
class WorkloadHost(AnsibleHost):
    management_ip: IPv4Interface
    workload_interface: WorkloadInterface

@dataclass(frozen=True, eq=True)
class SoftwareDefinedRadio:
    name: str
    mac_addr: str
    management_ip: IPv4Interface
    switch: SwitchConnection


