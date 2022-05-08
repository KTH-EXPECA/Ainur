from pathlib import Path

# from ainur import *
import click

from ainur.hosts import *
from ainur.networks import *
from ainur.swarm import *

# the workload switch, no need to change this
# should eventually go in a config file.
switch = Switch(
    name="glorfindel",
    management_ip=IPv4Interface("192.168.0.2/16"),
    username="cisco",
    password="expeca",
)

# hosts is a mapping from host name to a LocalAinurHost object
# note that the system determines how to connect devices using the ethernets
# and wifis dict.
# also note that if a device has more than one workload interface, ONLY ONE
# WILL BE USED (and it will be selected arbitrarily!)
hosts = {
    "workload-client-00": LocalAinurHost(
        management_ip=IPv4Interface("192.168.3.0/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(),
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
    "workload-client-01": LocalAinurHost(
        management_ip=IPv4Interface("192.168.3.1/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.1/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="7c:10:c9:1c:3f:ea",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    "workload-client-02": LocalAinurHost(
        management_ip=IPv4Interface("192.168.3.2/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.2/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="7c:10:c9:1c:3f:e8",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    "workload-client-03": LocalAinurHost(
        management_ip=IPv4Interface("192.168.3.3/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(),
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
    "workload-client-05": LocalAinurHost(
        management_ip=IPv4Interface("192.168.3.5/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.5/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="7c:10:c9:1c:3e:a8",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    "workload-client-06": LocalAinurHost(
        management_ip=IPv4Interface("192.168.3.6/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(),
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
    "workload-client-07": LocalAinurHost(
        management_ip=IPv4Interface("192.168.3.7/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.7/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="24:4b:fe:b7:26:92",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
    "workload-client-08": LocalAinurHost(
        management_ip=IPv4Interface("192.168.3.8/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(),
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
    "workload-client-09": LocalAinurHost(
        management_ip=IPv4Interface("192.168.3.9/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(),
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
    "workload-client-10": LocalAinurHost(
        management_ip=IPv4Interface("192.168.3.10/16"),
        ansible_user="expeca",  # cloud instances have a different user
        ethernets=frozendict(),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface("10.0.2.10/16"),
                routes=(
                    # this route is necessary to reach the VPN to the cloud
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"), via=IPv4Address("10.0.1.0")
                    ),
                ),
                mac="fc:34:97:25:a2:0d",
                ssid="expeca_wlan_1",  # SDR wifi ssid
            )
        ),
    ),
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


# noinspection DuplicatedCode
@click.command()
def deploy_swarm():
    ansible_ctx = AnsibleContext(base_dir=Path("ansible_env"))

    # prepare everything
    # if you dont want cloud instances, remove all CloudInstances and
    # VPNCloudMesh objects!
    # cloud = CloudInstances(
    #     region=region
    # )

    # this object merges and arbitrary number of VPN and local networks. it
    # can be left here if the VPN is removed.
    ip_layer = CompositeLayer3Network()

    lan_layer = ip_layer.add_network(
        LANLayer(ansible_context=ansible_ctx, ansible_quiet=False)
    )
    # vpn_mesh = ip_layer.add_network(
    #     VPNCloudMesh(
    #         gateway_ip=IPv4Address('130.237.53.70'),
    #         vpn_psk=os.environ['vpn_psk'],
    #         ansible_ctx=ansible_ctx,
    #         ansible_quiet=False
    #     )
    # )
    swarm = DockerSwarm()

    with ExitStack() as stack:
        # cloud = stack.enter_context(cloud)

        # start phy layer
        phy_layer: PhysicalLayer = stack.enter_context(
            PhysicalLayer(hosts=hosts, radio_aps=[], radio_stas=[], switch=switch)
        )

        # init layer 3 connectivity
        ip_layer: CompositeLayer3Network = stack.enter_context(ip_layer)
        lan_layer.add_hosts(phy_layer)

        # TODO: rework Swarm config to something less manual. Maybe fold in
        #  configs into general host specification somehow??
        # swarm is a bit manual for now.
        swarm: DockerSwarm = stack.enter_context(swarm)
        swarm.deploy_managers(
            hosts={hosts["elrond"]: {}}, location="edge", role="backend"
        ).deploy_workers(
            hosts={
                host: {}
                for name, host in hosts.items()
                if name.startswith("workload-client")
                # hosts['workload-client-01']: {}
            },
            role="client",
        )

        click.pause("Swarm is up and running; press any key to tear down.")


if __name__ == "__main__":
    deploy_swarm()
