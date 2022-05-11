from pathlib import Path

# from ainur import *
from typing import Literal

import click

from ainur.hosts import *
from ainur.networks import *
from ainur.swarm import *
from ainur_utils.hosts import get_hosts
from ainur_utils.resources import switch


# noinspection DuplicatedCode
@click.command()
@click.option(
    "-i",
    "--interface",
    type=click.Choice(("ethernet", "wifi")),
    default="ethernet",
    show_default=True,
)
@click.option(
    "-n",
    "--num-clients",
    type=click.IntRange(1, 10),
    default=10,
    show_default=True,
)
def deploy_swarm(interface: Literal["ethernet", "wifi"], num_clients: int):
    ansible_ctx = AnsibleContext(base_dir=Path("ansible_env"))
    hosts = get_hosts(num_clients, interface)

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
            PhysicalLayer(
                hosts=hosts,
                radio_aps=[
                    APSoftwareDefinedRadio(
                        name="RFSOM-00002",
                        management_ip=IPv4Interface("172.16.2.12/24"),
                        mac="02:05:f7:80:0b:19",
                        switch_port=42,
                        ssid="expeca_wlan_1",
                        net_name="eth_net",
                        channel=11,
                        beacon_interval=100,
                        ht_capable=True,
                    )
                ],
                radio_stas=[],
                switch=switch,
            )
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
