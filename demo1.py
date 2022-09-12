import os
from contextlib import ExitStack
from ipaddress import IPv4Address, IPv4Interface
from pathlib import Path
from typing import Literal

import click
from frozendict import frozendict

from ainur.ansible import AnsibleContext
from ainur.cloud import CloudInstances
from ainur.hosts import AinurCloudHostConfig, EthernetCfg, LocalAinurHost, WireSpec
from ainur.networks import CompositeLayer3Network, LANLayer, VPNCloudMesh
from ainur.physical import PhysicalLayer
from ainur.swarm import DockerSwarm
from ainur_utils.hosts import EDGE_HOST, get_hosts
from ainur_utils.resources import switch, get_aws_ami_id_for_region

AWS_REGION = "eu-north-1"

CLOUD_HOST = AinurCloudHostConfig(
    management_ip=IPv4Interface("172.16.0.2/24"),
    workload_ip=IPv4Interface("172.16.1.2/24"),
    ansible_user="ubuntu",
)

VPN_GW = LocalAinurHost(
    management_ip=IPv4Interface("192.168.0.4/16"),
    ansible_user="expeca",
    ethernets=frozendict(
        {
            "eth0": EthernetCfg(
                ip_address=IPv4Interface("10.0.1.0/16"),
                routes=(),
                mac="dc:a6:32:bf:54:1b",
                wire_spec=WireSpec(
                    net_name="eth_net",
                    switch_port=36,
                ),
            )
        }
    ),
    wifis=frozendict(),
)

AP_PORT = 5
WORKLOAD_NAME = "EWDEMO1"
DURATION = "1h"


def generate_workload_def(
    offload: Literal["local", "edge", "cloud"],
):
    # language=yaml
    return f"""
---
name: {WORKLOAD_NAME}
author: "Manuel Olguín Muñoz, Vishnu N. Moothedath"
email: "molguin@kth.se"
version: "1.0a"
url: "expeca.proj.kth.se"
max_duration: "{DURATION}"
compose:
  version: "3.9"
  services:
    server:
      image: expeca/demo_ew22_backend
      hostname: server
      deploy:
        replicas: 1
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.location=={offload}"
        restart_policy:
          condition: always
    client:
      image: expeca/demo_ew22_client
      hostname: client
      ports:
      - "80:8080/tcp"
      command:
        - "server"
      deploy:
        replicas: 1
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.role==client"
        restart_policy:
          condition: always
      depends_on:
      - server
...
"""


@click.command()
@click.option(
    "-l",
    "--offload",
    type=click.Choice(["local", "edge", "cloud"]),
    default="local",
    show_default=True,
    help="Where to offload the backend computation.",
)
@click.option(
    "-p",
    "--phy",
    type=click.Choice(["ethernet", "wifi"]),
    default="wifi",
    show_default=True,
    help="Phy layer to deploy.",
)
def main(
    offload: Literal["local", "edge", "cloud"],
    phy: Literal["ethernet", "wifi"],
):
    # get a random client host
    client_host, *_ = get_hosts(
        client_count=1,
        iface=phy,
        wifi_ssid="expeca_wlan_2",
        wifi_password="EXPECA-WLAN",
        wifi_hidden=True,
    )

    ansible_ctx = AnsibleContext(base_dir=Path("ansible_env"))

    cloud = CloudInstances(region=AWS_REGION)

    # combines layer3 networks
    ip_layer = CompositeLayer3Network()

    lan_layer = ip_layer.add_network(
        LANLayer(ansible_context=ansible_ctx, ansible_quiet=False)
    )

    # VPN layer for cloud instances
    vpn_mesh = ip_layer.add_network(
        VPNCloudMesh(
            gateway_ip=IPv4Address("130.237.53.70"),
            vpn_psk=os.environ["vpn_psk"],
            ansible_ctx=ansible_ctx,
            ansible_quiet=False,
        )
    )

    with ExitStack() as stack:
        # prepare cloud layer
        cloud: CloudInstances = stack.enter_context(cloud)
        cloud.init_instances(
            num_instances=1,
            ami_id=get_aws_ami_id_for_region(AWS_REGION),
        )

        # start phy layer
        phy_layer: PhysicalLayer = stack.enter_context(
            PhysicalLayer(
                hosts={},
                radio_aps=[],
                radio_stas=[],
                switch=switch,
            )
        )
        # hack to make vlan including AP, elrond, and the VPN GW
        switch_ports = [
            AP_PORT,
            EDGE_HOST.ethernets["enp4s0"].wire_spec.switch_port,
            VPN_GW.ethernets["eth0"].wire_spec.switch_port,
        ]
        phy_layer._switch.make_vlan(switch_ports, name="edgedroid_vlan")
        phy_layer._hosts = dict(
            client=client_host,
            elrond=EDGE_HOST,
            olwe=VPN_GW,
        )

        # init layer 3 connectivity
        ip_layer: CompositeLayer3Network = stack.enter_context(ip_layer)
        lan_layer.add_hosts(phy_layer)
        # connect the cloud
        vpn_mesh.connect_cloud(
            cloud_layer=cloud,
            host_configs=[CLOUD_HOST],
        )

        # init swarm
        swarm: DockerSwarm = stack.enter_context(DockerSwarm())
        swarm.deploy_managers(
            hosts={
                EDGE_HOST: dict(
                    location="edge",
                    role="backend",
                ),
            }
        ).deploy_workers(
            hosts={client_host: dict(role="client", location="local")}
        ).deploy_workers(
            hosts={CLOUD_HOST: dict(role="backend", location="cloud")}
        )

        click.pause()
