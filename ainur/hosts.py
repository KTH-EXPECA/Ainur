from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Interface
from typing import Dict, Literal, Optional

from dataclasses_json import config, dataclass_json


# Switch connection dataclass
@dataclass_json
@dataclass(frozen=True, eq=True)
class SwitchConnection:
    name: str
    port: int


@dataclass_json
@dataclass(frozen=True, eq=True)
class Switch:
    name: str
    management_ip: str
    username: str
    password: str


# SDR dataclass
@dataclass_json
@dataclass(frozen=True, eq=True)
class SoftwareDefinedRadio:
    name: str
    mac: str
    management_ip: IPv4Interface = field(
        metadata=config(
            encoder=str,
            decoder=IPv4Interface
        )
    )
    switch_connection: SwitchConnection


############
# Physical Layer Network Concept Representation Classes
@dataclass_json
@dataclass(frozen=True, eq=True)
class PhyNetwork:
    name: str


# WiFi network
@dataclass_json
@dataclass(frozen=True, eq=True)
class WiFiNetwork(PhyNetwork):
    ssid: str
    channel: int
    beacon_interval: int
    ht_capable: bool


# LTE network
@dataclass_json
@dataclass(frozen=True, eq=True)
class LTENetwork(PhyNetwork):
    TAC: str,
    MNC: str,
    MCC: str,
    HPLMN: str,
    LTE_K: str,
    OP_KEY: str,
    FIRST_MSIN: str,
    MAX_N_UE: int,
    downlink_frequency: int,
    uplink_frequency_offset: int,
    eutra_band: int,
    N_RB_DL: int,

# Wired network
@dataclass_json
@dataclass(frozen=True, eq=True)
class WiredNetwork(PhyNetwork):
    pass


############
# Hosts Physical Layer Representation Classes
@dataclass_json
@dataclass(frozen=True, eq=True)
class Phy:
    network: str  # corresponds to PhyNetwork name


@dataclass_json
@dataclass(frozen=True, eq=True)
class WiFi(Phy):
    is_ap: bool
    radio: str  # corresponds to SoftwareDefinedRadio or 'native'


@dataclass_json
@dataclass(frozen=True, eq=True)
class Wire(Phy):
    pass


@dataclass_json
@dataclass(frozen=True, eq=True)
class LTE(Phy):
    is_enb: bool    
    radio_host: str  # corresponds to the name of radiohost

############
# Workload Network Interface

@dataclass_json
@dataclass(frozen=True, eq=True)
class NetplanInterface:
    # wraps everything we need to know about specific interfaces, like their
    # MAC address, netplan type, etc.
    netplan_type: Literal['ethernets', 'wifis']
    name: str
    mac: str


@dataclass_json
@dataclass(frozen=True, eq=True)
class EthernetInterface(NetplanInterface):
    switch_connection: SwitchConnection
    netplan_type: Literal['ethernets'] = field(default='ethernets', init=False)


@dataclass_json
@dataclass(frozen=True, eq=True)
class WiFiInterface(NetplanInterface):
    netplan_type: Literal['wifis'] = field(default='wifis', init=False)


@dataclass_json
@dataclass(frozen=True, eq=True)
class ConnectionSpec:
    ip: IPv4Interface
    phy: Phy


############
# Workload Network Interface

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
    phy: Phy
    workload_interface: str  # Points toward the workload interface to use in L3


@dataclass_json
@dataclass(frozen=True, eq=True)
class Layer3ConnectedWorkloadHost(Layer2ConnectedWorkloadHost):
    workload_ip: IPv4Interface = field(
        metadata=config(
            encoder=str,
            decoder=IPv4Interface
        )
    )
    # TODO: fix?
    wifi_ssid: Optional[str] = field(default=None)

    def __str__(self) -> str:
        return f'{self.ansible_host} (management address ' \
               f'{self.management_ip}; workload address: {self.workload_ip})'
