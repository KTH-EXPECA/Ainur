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


## SDR dataclass
@dataclass(frozen=True, eq=True)
class SoftwareDefinedRadio:
    name: str
    mac_addr: str
    management_ip: IPv4Interface
    switch: SwitchConnection


## WiFi network dataclass
@dataclass(frozen=True, eq=True)
class WiFiNetwork():
    ssid: str
    channel: int
    beacon_interval: int
    ht_capable: bool

## Wired network dataclass
@dataclass(frozen=True, eq=True)
class WiredNetwork():
    name: str

############
## Physical Layer Representation Dataclasses
@dataclass(frozen=True, eq=True)
class Phy:
    pass

@dataclass(frozen=True, eq=True)
class WiFi(Phy):
    network: WiFiNetwork

@dataclass(frozen=True, eq=True)
class WiFiNative(WiFi):
    pass

@dataclass(frozen=True, eq=True)
class WiFiNativeSTA(WiFiNative):
    pass

@dataclass(frozen=True, eq=True)
class WiFiNativeAP(WiFiNative):
    pass

@dataclass(frozen=True, eq=True)
class WiFiSDR(WiFi):
    radio: SoftwareDefinedRadio 

@dataclass(frozen=True, eq=True)
class WiFiSDRAP(WiFiSDR):
    pass

@dataclass(frozen=True, eq=True)
class WiFiSDRSTA(WiFiSDR):
    pass
    
@dataclass(frozen=True, eq=True)
class Wire(Phy):
    network: WiredNetwork


############
## Workload Network Interface

@dataclass(frozen=True, eq=True)
class WorkloadInterface:
    name: str
    mac_addr: str

@dataclass(frozen=True, eq=True)
class EthernetInterface(WorkloadInterface):
    switch: SwitchConnection

@dataclass(frozen=True, eq=True)
class WiFiInterface(WorkloadInterface):
    pass




############
## Workload Network Interface

@dataclass(frozen=True, eq=True)
class AnsibleHost:
    ansible_host: str
    management_ip: IPv4Interface

@dataclass(frozen=True, eq=True)
class WorkloadHost(AnsibleHost):
    workload_interfaces: tuple(WorkloadInterface)

@dataclass(frozen=True, eq=True)
class ConnectedWorkloadHost(AnsibleHost):
    phy: Phy
    ip: IPv4Interface
    workload_interface: WorkloadInterface


