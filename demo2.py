#!/usr/bin/env python3

import io
import itertools
import os
from collections import deque
from pathlib import Path

import click

from ainur.hosts import *
from ainur.networks import *
from ainur.swarm import *
from ainur.swarm.storage import ExperimentStorage
from ainur_utils.hosts import EDGE_HOST, get_hosts
from ainur_utils.resources import get_aws_ami_id_for_region, switch

AP_PORT = 5

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

CLOUD_MGMT_NET = IPv4Network("172.16.0.0/24")
CLOUD_WKLD_NET = IPv4Network("172.16.1.0/24")


def gen_cloud_host_cfgs(num_hosts: int) -> List[AinurCloudHostConfig]:
    mgmt_hosts = deque()
    for net in CLOUD_MGMT_NET.address_exclude(IPv4Network("172.16.0.1/32")):
        for host in net.hosts():
            mgmt_hosts.append(host)

    wkld_hosts = deque()
    for net in CLOUD_WKLD_NET.address_exclude(IPv4Network("172.16.1.1/32")):
        for host in net.hosts():
            wkld_hosts.append(host)

    assert num_hosts <= len(wkld_hosts)

    return [
        AinurCloudHostConfig(
            management_ip=IPv4Interface(f"{mgmt_ip}/24"),
            workload_ip=IPv4Interface(f"{wkld_ip}/24"),
            ansible_user="ubuntu",
        )
        for mgmt_ip, wkld_ip, _ in zip(
            mgmt_hosts,
            wkld_hosts,
            itertools.repeat(None, num_hosts),
        )
    ]


# noinspection DuplicatedCode
@click.command()
@click.argument(
    "workload_definition",
    type=click.File("r"),
)
@click.option(
    "--dry-run",
    "dry_run",
    is_flag=True,
)
def run_experiment(
    workload_definition: io.FileIO,
    dry_run: bool = False,
):
    wkld_def: Dict[str, Any] = yaml.safe_load(workload_definition)
    cloud_cfg = wkld_def.pop("cloud")

    num_cloud_insts = cloud_cfg.get("instance_count", 0)
    has_cloud = num_cloud_insts > 0
    region = cloud_cfg.get("region", "eu-north-1")

    phy_cfg = wkld_def.pop("phy")

    # "guess" required number of clients
    num_clients = -float("inf")
    for serv_name, service in wkld_def["compose"]["services"].items():
        replicas = service.get("deploy", {}).get("replicas", 0)
        num_clients = max(num_clients, replicas)

    assert num_clients <= 10

    # noinspection PyTypeChecker
    client_hosts = get_hosts(
        client_count=num_clients,
        iface=phy_cfg["type"],
        wifi_ssid="expeca_wlan_2",
        wifi_password="EXPECA-WLAN",
        wifi_hidden=True,
    )

    ansible_ctx = AnsibleContext(base_dir=Path("ansible_env"))

    if has_cloud:
        cloud = CloudInstances(region=region)
        cloud_host_cfgs = gen_cloud_host_cfgs(num_cloud_insts)

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

    logger.info(
        f"Running experiment with {num_clients} local clients and "
        f"{num_cloud_insts} cloud compute instances!"
    )

    with ExitStack() as stack:
        # prepare cloud layer
        if has_cloud:
            cloud: CloudInstances = stack.enter_context(cloud)
            cloud.init_instances(
                num_instances=num_cloud_insts,
                ami_id=get_aws_ami_id_for_region(region),
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
            **client_hosts,
            elrond=EDGE_HOST,
            olwe=VPN_GW,
        )

        # init layer 3 connectivity
        ip_layer: CompositeLayer3Network = stack.enter_context(ip_layer)
        lan_layer.add_hosts(phy_layer)

        if has_cloud:
            # connect the cloud
            vpn_mesh.connect_cloud(
                cloud_layer=cloud,
                host_configs=cloud_host_cfgs,
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
            hosts={h: {} for _, h in client_hosts.items()},
            role="client",
        )

        if has_cloud:
            swarm.deploy_workers(
                hosts={h: {} for h in cloud_host_cfgs},
                role="backend",
                location="cloud",
            )

        # fetch images
        for serv_name, service in wkld_def["compose"]["services"].items():
            try:
                img, tag = service["image"].split(":")
            except ValueError:
                img = service["image"]
                tag = "latest"
            swarm.pull_image(image=img, tag=tag)

        workload = WorkloadSpecification.from_dict(wkld_def)

        if dry_run:
            logger.debug("Dry run")
            logger.debug(f"\n{workload.to_json(indent=4)}\n")
            click.pause("Pausing before shutdown!")
            return

        with ExperimentStorage(
            storage_name=workload.name,
            storage_host=ManagedHost(
                management_ip=IPv4Interface("192.168.1.1/16"),
                ansible_user="expeca",
            ),
            network=ip_layer,
            ansible_ctx=ansible_ctx,
            ansible_quiet=False,
        ) as storage:
            swarm.deploy_workload(
                specification=workload,
                attach_volume=storage.docker_vol_name,
                max_failed_health_checks=-1,
            )


if __name__ == "__main__":
    run_experiment()
