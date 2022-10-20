import itertools
import random
import tempfile
from pathlib import Path

import click

from ainur.hosts import *
from ainur.networks import *
from ainur.swarm import *
from ainur.swarm.storage import ExperimentStorage
from ainur_utils.hosts import EDGE_HOST, MAX_NUM_CLIENTS, get_hosts
from ainur_utils.resources import switch

# from ainur import *

AP_PORT = 5
IMAGE = "molguin/edgedroid2"
IPERF_IMG = "expeca/simple-network-load"
SERVER_TAG = "experiment-server"
CLIENT_TAG = "experiment-client"
TASK_SLOT = r"{{.Task.Slot}}"
SERVER_HOST = f"server{TASK_SLOT}"
CLIENT_HOST = f"client{TASK_SLOT}"
IPERF_SERVER_HOST = f"iperfserver{TASK_SLOT}"
IPERF_CLIENT_HOST = f"iperfclient{TASK_SLOT}"


def generate_workload_def(
    workload_name: str,
    num_clients: int,
    num_iperf_clients: int,
    run_n: int,
    task: str,
    truncate: int,
    experiment_id: str,
    max_duration: str,
    iperf_rate: str,
    iperf_time_seconds: int,
    iperf_start_delay_seconds: int,
    iperf_use_udp: bool,
    iperf_saturate: bool,
    iperf_streams: int,
    env_file: Path,
    collocate_iperf: bool,
    extra_server_delay: float,
) -> str:
    task_name = task if truncate < 0 else f"{task}-{truncate}"
    use_udp = str(iperf_use_udp).lower()
    saturate = str(iperf_saturate).lower()

    node_iperf = "yes" if collocate_iperf else "no"

    edgedroid_output = (
        f"/opt/results"
        f"/edgedroid-{experiment_id}-{task_name}"
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
    server:
      image: {IMAGE}:{SERVER_TAG}
      hostname: {SERVER_HOST}
      env_file:
      - {env_file.resolve()}
      environment:
        EDGEDROID_SERVER_OUTPUT_DIR: {edgedroid_output}
      command:
      - "--verbose"
      - "--truncate"
      - "{truncate}"
      - "--delay-seconds"
      - "{extra_server_delay:3f}"
      - "0.0.0.0"
      - "5000"
      - "{task}"
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
      env_file:
      - {env_file.resolve()}
      environment:
        EDGEDROID_CLIENT_HOST: {SERVER_HOST}
        EDGEDROID_CLIENT_PORT: 5000
        EDGEDROID_CLIENT_TRACE: "{task}"
        EDGEDROID_CLIENT_OUTPUT_DIR: {edgedroid_output}
      command:
        - "--truncate"
        - "{truncate}"
        - "--verbose"
        - "--connect-timeout-seconds"
        - "5.0"
        - "--max-connection-attempts"
        - "0"
        - "{experiment_id}"
      deploy:
        replicas: {num_clients:d}
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.role==client"
          - "node.labels.iperf=={node_iperf}"
        restart_policy:
          condition: none
      depends_on:
      - server
      
    iperfserver:
      image: {IPERF_IMG}:latest
      hostname: {IPERF_SERVER_HOST}
      environment:
        IPERF_LOG_HEADER: >-
            edgedroid-{experiment_id}
            task-{task}
            clients-{num_clients}
            run-{run_n}
        IPERF_LOGFILE: /opt/results/{IPERF_SERVER_HOST}.log
      command: iperf-server.sh
      deploy:
        replicas: {num_iperf_clients if not collocate_iperf else num_clients:d}
        placement:
          max_replicas_per_node: {num_iperf_clients:d}
          constraints:
          - "node.labels.role==backend"
          - "node.labels.iperf==yes"
        restart_policy:
          condition: any
      volumes:
        - type: volume
          source: {workload_name}
          target: /opt/results/
          volume:
            nocopy: true
            
    iperfclient:
      image: {IPERF_IMG}:latest
      hostname: {IPERF_CLIENT_HOST}
      volumes:
        - type: volume
          source: {workload_name}
          target: /opt/results/
          volume:
            nocopy: true
      environment:
        IPERF_LOG_HEADER: >-
            edgedroid-{experiment_id}
            task-{task}
            clients-{num_clients}
            run-{run_n}
        IPERF_SERVER_ADDR: {IPERF_SERVER_HOST}
        IPERF_TIME: {iperf_time_seconds:d}
        IPERF_BITRATE: {iperf_rate}
        IPERF_CONN_TIMEOUT: 1000
        IPERF_MAX_RETRIES: 600
        IPERF_START_DELAY: {iperf_start_delay_seconds}
        IPERF_LOGFILE: /opt/results/{IPERF_CLIENT_HOST}.log
        IPERF_USE_UDP: "{use_udp}"
        IPERF_SATURATE: "{saturate}"
        IPERF_STREAMS: {iperf_streams}
      command: iperf-client.sh
      deploy:
        replicas: {num_iperf_clients if not collocate_iperf else num_clients:d}
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.role==client"
          - "node.labels.iperf==yes"
        restart_policy:
          condition: none
      depends_on:
      - iperfserver
...
"""


# noinspection DuplicatedCode
@click.command()
@click.argument("workload-name", type=str)
@click.argument("experiment-ids", type=str, nargs=-1)
@click.option(
    "-n",
    "--num-clients",
    "num_clients",
    type=click.IntRange(0, MAX_NUM_CLIENTS, max_open=False),
    # multiple=True,
    default=MAX_NUM_CLIENTS,
    show_default=True,
)
@click.option(
    "-p",
    "--num-iperf-clients",
    "num_iperf_clients",
    type=click.IntRange(-1, MAX_NUM_CLIENTS, max_open=False),
    # multiple=True,
    default=0,
    show_default=True,
)
@click.option(
    "-d",
    "--max-duration",
    type=str,
    default="1h",
    show_default=True,
)
@click.option(
    "-t",
    "--task",
    "task",
    type=str,
    show_default=True,
    default="square00",
)
@click.option(
    "--truncate",
    type=int,
    default=-1,
    show_default=False,
)
@click.option(
    "--noconfirm",
    is_flag=True,
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
    "--iperf-rate",
    "iperf_rate",
    type=str,
    # multiple=True,
    default="50M",
    show_default=True,
)
@click.option(
    "--iperf-time-seconds",
    "iperf_seconds",
    type=int,
    default=10,
    show_default=True,
)
@click.option(
    "--iperf-start-delay-seconds",
    "iperf_delay",
    type=int,
    default=0,
    show_default=True,
)
@click.option(
    "--iperf-use-udp",
    "iperf_use_udp",
    is_flag=True,
)
@click.option(
    "-e",
    "--env",
    "envvars",
    type=str,
    default=(),
    multiple=True,
)
@click.option(
    "--iperf-saturate",
    "iperf_saturate",
    is_flag=True,
)
@click.option(
    "--iperf-streams",
    "iperf_streams",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
)
@click.option(
    "--extra-server-delay",
    type=float,
    default=0.0,
    show_default=True,
)
def run_experiment(
    workload_name: str,
    experiment_ids: Collection[str],
    num_clients: int,
    num_iperf_clients: int,
    max_duration: str,
    task: str,
    truncate: int,
    noconfirm: bool,
    repetitions: int,
    dry_run: bool,
    iperf_rate: str,
    iperf_seconds: int,
    iperf_delay: int,
    iperf_use_udp: bool,
    iperf_saturate: bool,
    iperf_streams: int,
    extra_server_delay: float,
    envvars: Collection[str],
):
    env_vars = {}
    for envvar in envvars:
        varname, value = envvar.split("=", 1)
        env_vars[varname.strip()] = value

    # workload client count and swarm size are not related
    interface = "wifi"
    # num_clients = set(num_clients)

    if num_iperf_clients < 0:
        collocate_iperf = True
        num_iperf_clients = 0
    else:
        collocate_iperf = False

    total_clients = num_iperf_clients + num_clients

    # noinspection PyTypeChecker
    client_hosts = get_hosts(
        client_count=total_clients,
        iface=interface,
        wifi_ssid="expeca_wlan_2",
        wifi_password="EXPECA-WLAN",
        wifi_hidden=True,
    )
    # backend_hosts = {"elrond": EDGE_HOST}

    ansible_ctx = AnsibleContext(base_dir=Path("ansible_env"))
    ip_layer = CompositeLayer3Network()

    lan_layer = ip_layer.add_network(
        LANLayer(ansible_context=ansible_ctx, ansible_quiet=False)
    )

    with ExitStack() as stack:
        # vars
        tmp_dir: Path = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        tmp_envfile = tmp_dir / f"EXPECA_{workload_name}.env"

        with tmp_envfile.open("w") as fp:
            for key, val in env_vars.items():
                print(f"{key}={val}", file=fp)

        # cloud = stack.enter_context(cloud)

        # start phy layer
        phy_layer: PhysicalLayer = stack.enter_context(
            PhysicalLayer(hosts={}, radio_aps=[], radio_stas=[], switch=switch)
        )
        # hack to make vlan including AP and elrond
        switch_ports = [
            AP_PORT,
            EDGE_HOST.ethernets["enp4s0"].wire_spec.switch_port,
        ]
        phy_layer._switch.make_vlan(switch_ports, name="edgedroid_vlan")
        phy_layer._hosts = dict(**client_hosts, elrond=EDGE_HOST)

        # init layer 3 connectivity
        ip_layer: CompositeLayer3Network = stack.enter_context(ip_layer)
        lan_layer.add_hosts(phy_layer)

        # iperf labels
        iperf_host_names = random.sample(
            client_hosts.keys(),
            k=num_iperf_clients,
        )
        worker_host_names = set(client_hosts.keys()).difference(iperf_host_names)

        logger.info(f"Edgedroid hosts: {worker_host_names}")
        logger.info(
            f"iPerf hosts: "
            f"{iperf_host_names if not collocate_iperf else worker_host_names}"
        )

        client_swarm_labels = {}
        for host_name in iperf_host_names:
            host = client_hosts[host_name]
            client_swarm_labels[host] = {"iperf": "yes", "role": "client"}

        for host_name in worker_host_names:
            host = client_hosts[host_name]
            client_swarm_labels[host] = {
                "iperf": "yes" if collocate_iperf else "no",
                "role": "client",
            }

        # init swarm
        swarm: DockerSwarm = stack.enter_context(DockerSwarm())
        swarm.deploy_managers(
            hosts={EDGE_HOST: {}},
            location="edge",
            role="backend",
            iperf="yes",
        ).deploy_workers(
            hosts=client_swarm_labels,
        )
        swarm.pull_image(image=IMAGE, tag=SERVER_TAG)
        swarm.pull_image(image=IMAGE, tag=CLIENT_TAG)
        swarm.pull_image(image=IPERF_IMG, tag="latest")

        configs = list(
            itertools.product(
                experiment_ids,
                range(repetitions),
            )
        )

        # shuffle configs to help avoiding experimental flukes
        for exp_id, run in random.sample(configs, k=len(configs)):
            workload: WorkloadSpecification = WorkloadSpecification.from_dict(
                yaml.safe_load(
                    generate_workload_def(
                        num_clients=num_clients,
                        num_iperf_clients=num_iperf_clients,
                        run_n=run + 1,
                        task=task,
                        truncate=truncate,
                        experiment_id=exp_id,
                        workload_name=workload_name,
                        max_duration=max_duration,
                        iperf_rate=iperf_rate,
                        iperf_start_delay_seconds=iperf_delay,
                        iperf_time_seconds=iperf_seconds,
                        iperf_use_udp=iperf_use_udp,
                        iperf_saturate=iperf_saturate,
                        env_file=tmp_envfile,
                        iperf_streams=iperf_streams,
                        collocate_iperf=collocate_iperf,
                        extra_server_delay=extra_server_delay,
                    )
                )
            )
            if dry_run:
                logger.debug(f"Dry run: {exp_id=} {task=} {truncate=} {run=}")
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
                    ignored_health_services=["iperfclient", "iperfserver"],
                )


if __name__ == "__main__":
    run_experiment()
