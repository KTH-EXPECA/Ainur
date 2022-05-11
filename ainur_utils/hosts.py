import random
from ipaddress import IPv4Address, IPv4Interface
from typing import Dict, List, Literal

from frozendict import frozendict

from ainur.hosts import (
    AinurCloudHostConfig,
    EthernetCfg,
    IPRoute,
    LocalAinurHost,
    WiFiCfg,
    WireSpec,
)

__all__ = [
    "get_hosts",
    "generate_cloud_host_configs",
    "MAX_NUM_EDGE",
    "MAX_NUM_CLIENTS",
]

CLIENT_HOSTS = {
    "workload-client-00": dict(
        management_ip=IPv4Interface("192.168.3.0/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(
            {
                "eth0": EthernetCfg(
                    ip_address=IPv4Interface("10.0.2.0/16"),
                    routes=(
                        IPRoute(
                            to=IPv4Interface("172.16.1.0/24"),
                            via=IPv4Address("10.0.1.0"),
                        ),
                    ),
                    mac="dc:a6:32:b4:d8:b5",
                    wire_spec=WireSpec(net_name="eth_net", switch_port=25),
                ),
            }
        ),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.0/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="7c:10:c9:1c:3f:f0",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    "workload-client-01": dict(
        management_ip=IPv4Interface("192.168.3.1/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(
            {
                "eth0": EthernetCfg(
                    ip_address=IPv4Interface("10.0.2.1/16"),
                    routes=(
                        IPRoute(
                            to=IPv4Interface("172.16.1.0/24"),
                            via=IPv4Address("10.0.1.0"),
                        ),
                    ),
                    mac="dc:a6:32:bf:53:04",
                    wire_spec=WireSpec(net_name="eth_net", switch_port=26),
                ),
            }
        ),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.1/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="dc:a6:32:bf:53:05",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    "workload-client-02": dict(
        management_ip=IPv4Interface("192.168.3.2/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(
            {
                "eth0": EthernetCfg(
                    ip_address=IPv4Interface("10.0.2.2/16"),
                    routes=(
                        IPRoute(
                            to=IPv4Interface("172.16.1.0/24"),
                            via=IPv4Address("10.0.1.0"),
                        ),
                    ),
                    mac="dc:a6:32:bf:52:95",
                    wire_spec=WireSpec(net_name="eth_net", switch_port=27),
                ),
            }
        ),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.2/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="dc:a6:32:bf:52:96",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    "workload-client-03": dict(
        management_ip=IPv4Interface("192.168.3.3/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(
            {
                "eth0": EthernetCfg(
                    ip_address=IPv4Interface("10.0.2.3/16"),
                    routes=(
                        IPRoute(
                            to=IPv4Interface("172.16.1.0/24"),
                            via=IPv4Address("10.0.1.0"),
                        ),
                    ),
                    mac="dc:a6:32:bf:52:a1",
                    wire_spec=WireSpec(net_name="eth_net", switch_port=28),
                ),
            }
        ),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.3/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="7c:10:c9:1c:3e:04",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    # client-04 is not working
    "workload-client-05": dict(
        management_ip=IPv4Interface("192.168.3.5/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(
            {
                "eth0": EthernetCfg(
                    ip_address=IPv4Interface("10.0.2.5/16"),
                    routes=(
                        IPRoute(
                            to=IPv4Interface("172.16.1.0/24"),
                            via=IPv4Address("10.0.1.0"),
                        ),
                    ),
                    mac="dc:a6:32:07:fe:f2",
                    wire_spec=WireSpec(net_name="eth_net", switch_port=30),
                ),
            }
        ),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.5/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="dc:a6:32:07:fe:f3",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    "workload-client-06": dict(
        management_ip=IPv4Interface("192.168.3.6/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(
            {
                "eth0": EthernetCfg(
                    ip_address=IPv4Interface("10.0.2.6/16"),
                    routes=(
                        IPRoute(
                            to=IPv4Interface("172.16.1.0/24"),
                            via=IPv4Address("10.0.1.0"),
                        ),
                    ),
                    mac="dc:a6:32:bf:53:f4",
                    wire_spec=WireSpec(net_name="eth_net", switch_port=31),
                ),
            }
        ),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.6/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="fc:34:97:25:a2:92",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    "workload-client-07": dict(
        management_ip=IPv4Interface("192.168.3.7/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(
            {
                "eth0": EthernetCfg(
                    ip_address=IPv4Interface("10.0.2.7/16"),
                    routes=(
                        IPRoute(
                            to=IPv4Interface("172.16.1.0/24"),
                            via=IPv4Address("10.0.1.0"),
                        ),
                    ),
                    mac="dc:a6:32:bf:52:83",
                    wire_spec=WireSpec(net_name="eth_net", switch_port=32),
                ),
            }
        ),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.7/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="dc:a6:32:bf:52:84",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    "workload-client-08": dict(
        management_ip=IPv4Interface("192.168.3.8/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(
            {
                "eth0": EthernetCfg(
                    ip_address=IPv4Interface("10.0.2.8/16"),
                    routes=(
                        IPRoute(
                            to=IPv4Interface("172.16.1.0/24"),
                            via=IPv4Address("10.0.1.0"),
                        ),
                    ),
                    mac="dc:a6:32:bf:54:12",
                    wire_spec=WireSpec(net_name="eth_net", switch_port=33),
                ),
            }
        ),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.8/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="dc:a6:32:bf:54:13",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    "workload-client-09": dict(
        management_ip=IPv4Interface("192.168.3.9/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(
            {
                "eth0": EthernetCfg(
                    ip_address=IPv4Interface("10.0.2.9/16"),
                    routes=(
                        IPRoute(
                            to=IPv4Interface("172.16.1.0/24"),
                            via=IPv4Address("10.0.1.0"),
                        ),
                    ),
                    mac="dc:a6:32:bf:53:40",
                    wire_spec=WireSpec(net_name="eth_net", switch_port=34),
                ),
            }
        ),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.9/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="3c:7c:3f:a2:50:bd",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    "workload-client-10": dict(
        management_ip=IPv4Interface("192.168.3.10/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(
            {
                "eth0": EthernetCfg(
                    ip_address=IPv4Interface("10.0.2.10/16"),
                    routes=(
                        IPRoute(
                            to=IPv4Interface("172.16.1.0/24"),
                            via=IPv4Address("10.0.1.0"),
                        ),
                    ),
                    mac="dc:a6:32:bf:52:b0",
                    wire_spec=WireSpec(net_name="eth_net", switch_port=35),
                ),
            }
        ),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.10/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="dc:a6:32:bf:52:b1",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
}

EDGE_HOSTS = {
    "elrond": LocalAinurHost(
        management_ip=IPv4Interface("192.168.1.2/16"),
        ansible_user="expeca",
        ethernets=frozendict(
            {
                "enp4s0": EthernetCfg(
                    ip_address=IPv4Interface("10.0.1.1/16"),
                    routes=(  # VPN route
                        IPRoute(
                            to=IPv4Interface("172.16.1.0/24"),
                            via=IPv4Address("10.0.1.0"),
                        ),
                    ),
                    mac="d8:47:32:a3:25:20",
                    wire_spec=WireSpec(
                        net_name="eth_net",
                        switch_port=2,
                    ),
                )
            }
        ),
        wifis=frozendict(),
    ),
}

MAX_NUM_CLIENTS = len(CLIENT_HOSTS)
MAX_NUM_EDGE = len(EDGE_HOSTS)


# hosts is a mapping from host name to a LocalAinurHost object
# note that the system determines how to connect devices using the ethernets
# and wifis dict.
# also note that if a device has more than one workload interface, ONLY ONE
# WILL BE USED (and it will be selected arbitrarily!)
def get_hosts(
    client_count: int,
    iface: Literal["wifi", "ethernet"],
) -> Dict[str, LocalAinurHost]:
    assert client_count <= len(CLIENT_HOSTS)

    keys = random.sample(
        population=CLIENT_HOSTS.keys(),
        k=client_count,
    )

    hosts = EDGE_HOSTS.copy()
    for k in keys:
        hd = CLIENT_HOSTS[k].copy()
        if iface == "wifi":
            hd["ethernets"] = frozendict()
        elif iface == "ethernet":
            hd["wifis"] = frozendict()
        else:
            raise NotImplementedError(f"Unrecognized interface: {iface}")

        hosts[k] = LocalAinurHost(**hd)

    return hosts


def generate_cloud_host_configs(count: int) -> List[AinurCloudHostConfig]:
    assert count <= 253
    return [
        AinurCloudHostConfig(
            management_ip=IPv4Interface(f"172.16.0.{i}/24"),
            workload_ip=IPv4Interface(f"172.16.1.{i}/24"),
            ansible_user="ubuntu",
        )
        for i in range(2, count + 2)
    ]
