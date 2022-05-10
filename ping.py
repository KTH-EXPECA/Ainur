from pathlib import Path

# from ainur import *
from typing import Literal

import click

from ainur.hosts import *
from ainur.networks import *
from ainur.swarm import *
from ainur.swarm.storage import ExperimentStorage
from ainur_utils.hosts import MAX_NUM_CLIENTS, get_hosts
from ainur_utils.resources import switch

sdr_aps = [
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
]

IMAGE = "alpine"
SERVER_TAG = "latest"
CLIENT_TAG = "latest"
TASK_SLOT = r"{{.Task.Slot}}"
SERVER_HOST = f"server{TASK_SLOT}"
CLIENT_HOST = f"client{TASK_SLOT}"
PING_CMD = r'"ping \$HOST | tee \$OUTPUT"'


def generate_workload_def(
    num_clients: int,
    workload_name: str,
    duration: str = "5m",
) -> str:
    # language=yaml
    return rf"""
---
name: {workload_name}
author: "Manuel Olguín Muñoz"
email: "molguin@kth.se"
version: "1.0a"
url: "expeca.proj.kth.se"
max_duration: "{duration}"
compose:
  version: "3.9"
  services:
    server:
      image: {IMAGE}:{SERVER_TAG}
      hostname: {SERVER_HOST}
      environment:
        HOST: {CLIENT_HOST}
        OUTPUT: /opt/results/{SERVER_HOST}.log
      command:
        - "sh"
        - "-c"
        - {PING_CMD}
      deploy:
        replicas: {num_clients:d}
        placement:
          max_replicas_per_node: {num_clients:d}
          constraints:
          - "node.labels.role==backend"
        restart_policy:
          condition: none
      volumes:
        - type: volume
          source: {workload_name}
          target: /opt/results/
          volume:
            nocopy: true
  
    client:
      image: {IMAGE}:{CLIENT_TAG}
      hostname: {CLIENT_HOST}
      environment:
        HOST: {SERVER_HOST}
        OUTPUT: /opt/results/{CLIENT_HOST}.log
      command: 
        - "sh"
        - "-c"
        - {PING_CMD}
      deploy:
        replicas: {num_clients:d}
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.role==client"
        restart_policy:
          condition: none
      volumes:
        - type: volume
          source: {workload_name}
          target: /opt/results/
          volume:
            nocopy: true
...
"""


# noinspection DuplicatedCode
@click.command()
@click.argument("workload-name", type=str)
@click.argument(
    "num-clients",
    type=click.IntRange(0, MAX_NUM_CLIENTS, max_open=False),
)
@click.argument(
    "duration",
    type=str,
)
@click.option(
    "-i",
    "--interface",
    type=click.Choice(["wifi", "ethernet"]),
    default="ethernet",
    show_default=True,
)
@click.option(
    "--noconfirm",
    is_flag=True,
)
def run_experiment(
    workload_name: str,
    duration: str,
    num_clients: int,
    interface: Literal["wifi", "ethernet"],
    noconfirm: bool,
):
    hosts = get_hosts(client_count=num_clients, iface=interface)

    ansible_ctx = AnsibleContext(base_dir=Path("ansible_env"))
    workload: WorkloadSpecification = WorkloadSpecification.from_dict(
        yaml.safe_load(
            generate_workload_def(
                num_clients=num_clients,
                duration=duration,
                workload_name=workload_name,
            )
        )
    )

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

    # TODO: rework Phy to also be "preparable"
    # TODO: same for experiment storage

    with ExitStack() as stack:
        # cloud = stack.enter_context(cloud)

        # start phy layer
        phy_layer: PhysicalLayer = stack.enter_context(
            PhysicalLayer(hosts=hosts, radio_aps=sdr_aps, radio_stas=[], switch=switch)
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

        # start cloud instances
        # cloud.init_instances(len(cloud_hosts), ami_id=ami_ids[region])
        # vpn_mesh.connect_cloud(
        #     cloud_layer=cloud,
        #     host_configs=cloud_hosts
        # )
        #
        # swarm.deploy_workers(hosts={host: {} for host in cloud_hosts},
        #                      role='backend', location='cloud')

        # pull the desired workload images ahead of starting the workload
        swarm.pull_image(image=IMAGE, tag=SERVER_TAG)
        swarm.pull_image(image=IMAGE, tag=CLIENT_TAG)

        storage: ExperimentStorage = stack.enter_context(
            ExperimentStorage(
                storage_name=workload.name,
                storage_host=ManagedHost(
                    management_ip=IPv4Interface("192.168.1.1/16"),
                    ansible_user="expeca",
                ),
                network=ip_layer,
                ansible_ctx=ansible_ctx,
                ansible_quiet=False,
            )
        )

        if not noconfirm:
            click.confirm(
                f"Ping workload is ready to run on {num_clients} clients.\n\n"
                f"Continue?",
                default=True,
                abort=True,
            )

        swarm.deploy_workload(
            specification=workload,
            attach_volume=storage.docker_vol_name,
            max_failed_health_checks=-1,
        )


if __name__ == "__main__":
    run_experiment()
