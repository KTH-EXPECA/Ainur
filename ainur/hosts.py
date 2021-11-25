from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import IPv4Interface

_ip_regex = re.compile('((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\\.|$)){4}')


## Switch connection dataclass
@dataclass(frozen=True, eq=True)
class SwitchConnection:
    name: str
    port: int

@dataclass(frozen=True, eq=True)
class Switch:
    name: str
    management_ip: str
    username: str
    password: str

## SDR dataclass
@dataclass(frozen=True, eq=True)
class SoftwareDefinedRadio:
    name: str
    mac_addr: str
    management_ip: IPv4Interface
    switch_connection: SwitchConnection


############
## Physical Layer Network Concept Representation Classes
@dataclass(frozen=True, eq=True)
class PhyNetwork():
    name: str

## WiFi network
@dataclass(frozen=True, eq=True)
class WiFiNetwork(PhyNetwork):
    ssid: str
    channel: int
    beacon_interval: int
    ht_capable: bool

## Wired network
@dataclass(frozen=True, eq=True)
class WiredNetwork(PhyNetwork):
    pass

############
## Hosts Physical Layer Representation Classes
@dataclass(frozen=True, eq=True)
class Phy:
    network: str    # corresponds to PhyNetwork name
    
@dataclass(frozen=True, eq=True)
class WiFi(Phy):
    is_ap: bool
    radio: str      # corresponds to SoftwareDefinedRadio or 'native'
    
@dataclass(frozen=True, eq=True)
class Wire(Phy):
    pass



############
## Workload Network Interface

@dataclass(frozen=True, eq=True)
class WorkloadInterface:
    name: str
    mac_addr: str

@dataclass(frozen=True, eq=True)
class EthernetInterface(WorkloadInterface):
    switch_connection: SwitchConnection

@dataclass(frozen=True, eq=True)
class WiFiInterface(WorkloadInterface):
    pass

@dataclass(frozen=True, eq=True)
class ConnectionSpec:
    ip: IPv4Interface
    phy: Phy

############
## Workload Network Interface

@dataclass(frozen=True, eq=True)
class AnsibleHost:
    ansible_host: str
    management_ip: IPv4Interface

@dataclass(frozen=True, eq=True)
class WorkloadHost(AnsibleHost):
    workload_interfaces: dict

@dataclass(frozen=True, eq=True)
class ConnectedWorkloadHost(AnsibleHost):
    phy: Phy
    ip: IPv4Interface
    connected_interface: str


