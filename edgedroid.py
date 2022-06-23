import itertools
from pathlib import Path

# from ainur import *
from typing import Sequence

import click

from ainur.hosts import *
from ainur.networks import *
from ainur.swarm import *
from ainur.swarm.storage import ExperimentStorage
from ainur_utils.hosts import MAX_NUM_CLIENTS, get_hosts
from ainur_utils.resources import switch

AP_PORT = 5

# SDR access point configurations for this workload scenario
# note that SDRs are no longer associated to hosts, but rather to the network
# as a whole.
# The switch connects the port of the sdr to the rest of the network (
# according to the net_name parameter) so that devices connected by wifi and
# devices on the wire can talk to each other (and so devices connected by
# wifi can reach the cloud! this is important).
# sdr_aps = [
#     APSoftwareDefinedRadio(
#         name="RFSOM-00002",
#         management_ip=IPv4Interface("172.16.2.12/24"),
#         mac="02:05:f7:80:0b:19",
#         switch_port=42,
#         ssid="expeca_wlan_1",
#         net_name="eth_net",
#         channel=11,
#         beacon_interval=100,
#         ht_capable=True,
#     )
# ]
#
# # sdr STA configurations
# sdr_stas = [
#     # StationSoftwareDefinedRadio(
#     #     name='RFSOM=00001',
#     #     management_ip=IPv4Interface('172.16.2.11/24'),
#     #     mac='02:05:f7:80:0b:72',
#     #     ssid='eth_net',
#     #     net_name='eth_net',
#     #     switch_port=41
#     # ),
#     # StationSoftwareDefinedRadio(
#     #     name='RFSOM=00003',
#     #     management_ip=IPv4Interface('172.16.2.13/24'),
#     #     mac='02:05:f7:80:02:c8',
#     #     ssid='eth_net',
#     #     net_name='eth_net',
#     #     switch_port=43
#     # ),
# ]

IMAGE = "molguin/edgedroid2"
IPERF_IMG = "molguin/iperf3-alpine"
SERVER_TAG = "server"
CLIENT_TAG = "client"
TASK_SLOT = r"{{.Task.Slot}}"
SERVER_HOST = f"server{TASK_SLOT}"
CLIENT_HOST = f"client{TASK_SLOT}"

TASK = "square00"


def generate_workload_def(
    num_clients: int,
    run_n: int,
    # task: str,
    model: str,
    workload_name: str,
    max_duration: str = "40m",
    neuroticism: float = 0.5,
    sampling_strategy: str = "zero-wait",
) -> str:
    edgedroid_output = (
        f"/opt/results"
        f"/neuro-{neuroticism}_model-{model}_sampling-{sampling_strategy}"
        f"/clients-{num_clients}"
        f"/run-{run_n}"
        f"/loop{TASK_SLOT}"
    )

    # language=yaml
    return f"""
---
name: {workload_name}
author: "Manuel Olguín Muñoz"
email: "molguin@kth.se"
version: "1.0a"
url: "expeca.proj.kth.se"
max_duration: "{max_duration}"
compose:
  version: "3.9"
  services:
#    iperf3-server:
#      image: molguin/iperf3-alpine:latest
#      hostname: iperf
#      command:
#      - "-s"
#      - "-p"
#      - "1337"
#      - "--one-off"
#      - "--logfile"
#      - "/opt/results/iperf-server.log"
#      - "--forceflush"
#      deploy:
#        replicas: 1
#        placement:
#          max_replicas_per_node: 1
#          constraints:
#          - "node.labels.role==backend"
#          - "node.labels.iperf==yes"
#        restart_policy:
#          condition: on-failure
#          max_attempts: 3
#      volumes:
#      - type: volume
#        source: {workload_name}
#        target: /opt/results/
#        volume:
#          nocopy: true
#    
#    iperf3-client:
#      image: molguin/iperf3-alpine:latest
#      command:
#      - "-c"
#      - "iperf"
#      - "-p"
#      - "1337"
#      - "-b"
#      - "iperf_rate"
#      - "-t"
#      - "0"
#      - "--reverse"
#      - "--logfile"
#      - "/opt/results/iperf-client.log"
#      - "--forceflush"
#      deploy:
#        replicas: 1
#        placement:
#          max_replicas_per_node: 1
#          constraints:
#          - "node.labels.role==client"
#          - "node.labels.iperf==yes"
#        restart_policy:
#          condition: on-failure
#          max_attempts: 3
#      volumes:
#      - type: volume
#        source: {workload_name}
#        target: /opt/results/
#        volume:
#          nocopy: true
#      depends_on:
#      - iperf3-server
  
    server:
      image: {IMAGE}:{SERVER_TAG}
      hostname: {SERVER_HOST}
      environment:
        EDGEDROID_OUTPUT_DIR: {edgedroid_output}
      command:
      - "--verbose"
      - "0.0.0.0"
      - "5000"
      - "{TASK}"
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
      volumes:
        - type: volume
          source: {workload_name}
          target: /opt/results/
          volume:
            nocopy: true
      environment:
        EDGEDROID_CLIENT_HOST: {SERVER_HOST}
        EDGEDROID_CLIENT_PORT: 5000
        EDGEDROID_OUTPUT_DIR: {edgedroid_output}
      command:
        - "-n"
        - "{neuroticism}"
        - "-t"
        - "{TASK}"
        - "-f"
        - "8"
        - "-m"
        - "{model}"
        - "-s"
        - "{sampling_strategy}"
        - "--verbose"
        - "--connect-timeout-seconds"
        - "5.0"
        - "--max-connection-attempts"
        - "0"
      deploy:
        replicas: {num_clients:d}
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.role==client"
          - "node.labels.iperf==no"
        restart_policy:
          condition: none
      depends_on:
      - server
...
"""


# noinspection DuplicatedCode
@click.command()
@click.argument("workload-name", type=str)
@click.argument(
    "num-clients",
    type=click.IntRange(0, MAX_NUM_CLIENTS, max_open=False),
    nargs=-1,
)
@click.option(
    "-n",
    "--neuroticism",
    type=click.FloatRange(
        min=0,
        max=1.0,
        min_open=False,
        max_open=False,
        clamp=True,
    ),
    default=0.5,
    show_default=True,
)
@click.option(
    "-d",
    "--max-duration",
    type=str,
    default="1h",
    show_default=True,
)
# @click.option(
#     "-t",
#     "--task",
#     "tasks",
#     type=str,
#     multiple=True,
#     show_default=True,
#     default=("square00",),
# )
@click.option(
    "-m",
    "--model",
    "models",
    type=str,
    multiple=True,
    show_default=True,
    default=("naive", "empirical", "theoretical"),
)
# @click.option(
#     "-i",
#     "--interface",
#     type=click.Choice(["wifi", "ethernet"]),
#     default="ethernet",
#     show_default=True,
# )
@click.option(
    "--noconfirm",
    is_flag=True,
)
@click.option(
    "--swarm-size",
    type=int,
    default=10,
    show_default=True,
)
@click.option(
    "-r",
    "--repetitions",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Brings up everything up to the Swarm, but doesn't run workloads.",
)
@click.option(
    "--iperf",
    is_flag=True,
)
# @click.option(
#     "--iperf-rate",
#     "iperf_rates",
#     type=str,
#     multiple=True,
#     default=("50M",),
#     show_default=True,
# )
@click.option(
    "-s",
    "--sampling-strategy",
    "sampling_strategies",
    type=str,
    multiple=True,
    default=("zero-wait",),
    show_default=True,
)
def run_experiment(
    workload_name: str,
    num_clients: Sequence[int],
    neuroticism: float,
    max_duration: str,
    # tasks: Sequence[str],
    models: Sequence[str],
    # interface: Literal["wifi", "ethernet"],
    noconfirm: bool,
    swarm_size: int,
    repetitions: int,
    dry_run: bool,
    # iperf: bool,
    # iperf_rates: Sequence[str],
    sampling_strategies: Sequence[str],
):
    # workload client count and swarm size are not related
    interface = "wifi"
    num_clients = set(num_clients)

    # if iperf:
    #     for n in num_clients:
    #         if n > 9:
    #             raise RuntimeError(
    #                 "Maximum number of clients is 9 when running "
    #                 "iperf instance concurrently."
    #             )

    hosts = get_hosts(
        client_count=swarm_size,
        iface=interface,
        wifi_ssid="expeca_wlan_2",
        wifi_password="EXPECA-WLAN",
        wifi_hidden=True,
    )

    ansible_ctx = AnsibleContext(base_dir=Path("ansible_env"))
    ip_layer = CompositeLayer3Network()

    lan_layer = ip_layer.add_network(
        LANLayer(ansible_context=ansible_ctx, ansible_quiet=False)
    )

    with ExitStack() as stack:
        # cloud = stack.enter_context(cloud)

        # start phy layer
        phy_layer: PhysicalLayer = stack.enter_context(
            PhysicalLayer(hosts={}, radio_aps=[], radio_stas=[], switch=switch)
        )
        # hack to make vlan including AP and elrond
        switch_ports = [
            AP_PORT,
            hosts["elrond"].ethernets["enp4s0"].wire_spec.switch_port,
        ]
        phy_layer._switch.make_vlan(switch_ports, name="edgedroid_vlan")
        phy_layer._hosts = hosts.copy()

        # init layer 3 connectivity
        ip_layer: CompositeLayer3Network = stack.enter_context(ip_layer)
        lan_layer.add_hosts(phy_layer)

        # iperf label
        worker_hosts = {
            host: {"iperf": "no", "role": "client"}
            for name, host in hosts.items()
            if name.startswith("workload-client")
        }

        # if iperf:
        #     iperf_host = random.choice(list(worker_hosts))
        #     worker_hosts[iperf_host]["iperf"] = "yes"

        # init swarm
        swarm: DockerSwarm = stack.enter_context(DockerSwarm())
        swarm.deploy_managers(
            hosts={hosts["elrond"]: {}},
            location="edge",
            role="backend",
            # iperf="yes" if iperf else "no",
            iperf="no",
        ).deploy_workers(
            hosts=worker_hosts,
            role="client",
        )
        swarm.pull_image(image=IMAGE, tag=SERVER_TAG)
        swarm.pull_image(image=IMAGE, tag=CLIENT_TAG)
        swarm.pull_image(image=IPERF_IMG, tag="latest")

        for num, sampling, run, model in itertools.product(
            num_clients,
            sampling_strategies,
            # tasks,
            # iperf_rates,
            range(repetitions),
            models,
        ):
            # if iperf:
            #     wkld_name = (
            #         f"{workload_name}_Clients{num}_iperf{iperf_rate}_Run{run + 1}"
            #     )
            # else:
            #     wkld_name = f"{workload_name}_Clients{num}_Run{run + 1}"

            workload: WorkloadSpecification = WorkloadSpecification.from_dict(
                yaml.safe_load(
                    generate_workload_def(
                        num_clients=num,
                        run_n=run,
                        # task=task,
                        model=model,
                        workload_name=workload_name,
                        max_duration=max_duration,
                        neuroticism=neuroticism,
                        # iperf_rate=iperf_rate,
                        sampling_strategy=sampling,
                    )
                )
            )
            if dry_run:
                logger.debug(f"Dry run: {num=} | {model=} | {run=}")
                logger.debug(f"\n{workload.to_json(indent=4)}\n")
                continue

            # storage is restarted for each run
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
                if not noconfirm:
                    click.confirm(
                        f"Workload {workload_name} is ready to run.\n\nContinue?",
                        default=True,
                        abort=True,
                    )

                swarm.deploy_workload(
                    specification=workload,
                    attach_volume=storage.docker_vol_name,
                    max_failed_health_checks=-1,
                    ignored_health_services=["iperf3-client", "iperf3-server"],
                )


if __name__ == "__main__":
    run_experiment()
