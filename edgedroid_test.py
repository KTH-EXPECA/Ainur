import itertools
from pathlib import Path

# from ainur import *
from ainur.hosts import *
from ainur.networks import *
from ainur.swarm import *
from ainur.swarm.storage import ExperimentStorage

# used to indentify the correct virtual machine image to use for each AWS region
with open("./offload-ami-ids.yaml", "r") as fp:
    ami_ids = yaml.safe_load(fp)
region = "eu-north-1"
# region = 'us-east-1'

# the workload switch, no need to change this
# should eventually go in a config file.
switch = Switch(
    name="glorfindel",
    management_ip=IPv4Interface("192.168.0.2/16"),
    username="cisco",
    password="expeca",
)

# SDR access point configurations for this workload scenario
# note that SDRs are no longer associated to hosts, but rather to the network
# as a whole.
# The switch connects the port of the sdr to the rest of the network (
# according to the net_name parameter) so that devices connected by wifi and
# devices on the wire can talk to each other (and so devices connected by
# wifi can reach the cloud! this is important).
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

# sdr STA configurations
sdr_stas = [
    # StationSoftwareDefinedRadio(
    #     name='RFSOM=00001',
    #     management_ip=IPv4Interface('172.16.2.11/24'),
    #     mac='02:05:f7:80:0b:72',
    #     ssid='eth_net',
    #     net_name='eth_net',
    #     switch_port=41
    # ),
    # StationSoftwareDefinedRadio(
    #     name='RFSOM=00003',
    #     management_ip=IPv4Interface('172.16.2.13/24'),
    #     mac='02:05:f7:80:02:c8',
    #     ssid='eth_net',
    #     net_name='eth_net',
    #     switch_port=43
    # ),
]

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

# configurations for cloud hosts
# we only specify the desired ip addresses for the VPN networks and let AWS
# handle the rest.
cloud_hosts = [
    # AinurCloudHostConfig(
    #     management_ip=IPv4Interface('172.16.0.2/24'),
    #     workload_ip=IPv4Interface('172.16.1.2/24'),
    #     ansible_user='ubuntu',
    # ),
    # AinurCloudHostConfig(
    #     management_ip=IPv4Interface('172.16.0.3/24'),
    #     workload_ip=IPv4Interface('172.16.1.3/24'),
    #     ansible_user='ubuntu',
    # ),
    # AinurCloudHostConfig(
    #     management_ip=IPv4Interface('172.16.0.4/24'),
    #     workload_ip=IPv4Interface('172.16.1.4/24'),
    #     ansible_user='ubuntu',
    # ),
]

IMAGE = "molguin/edgedroid2"
SERVER_TAG = "server"
CLIENT_TAG = "client"
TASK_SLOT = r"{{.Task.Slot}}"


# SERVER_HOST = f"server"  # {TASK_SLOT}"
# CLIENT_HOST = f"client"  # {TASK_SLOT}"


def generate_workload_def(
    task: str,
    model: str,
    workload_name: str,
    duration: str = "40m",
) -> str:
    # language=yaml
    return f"""
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
      environment:
        EDGEDROID_SERVER_OUTPUT: /opt/results/server{TASK_SLOT}_{task}_{model}.csv
        EDGEDROID_SERVER_LOG_FILE: /opt/results/server{TASK_SLOT}_{task}_{model}.log
      command:
      - "--one-shot"
      - "--verbose"
      - "0.0.0.0"
      - "5000"
      - "{task}"
      deploy:
        replicas: 10
        placement:
          max_replicas_per_node: 10
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
      volumes:
        - type: volume
          source: {workload_name}
          target: /opt/results/
          volume:
            nocopy: true
      environment:
        EDGEDROID_CLIENT_HOST: server
        EDGEDROID_CLIENT_PORT: 5000
        EDGEDROID_CLIENT_OUTPUT: /opt/results/client{TASK_SLOT}_{task}_{model}.csv
        EDGEDROID_CLIENT_LOG_FILE: /opt/results/client{TASK_SLOT}_{task}_{model}.log
      command:
        - "-n"
        - "0.5"
        - "-t"
        - "{task}"
        - "-f"
        - "8"
        - "-m"
        - "{model}"
        - "--verbose"
        - "--connect-timeout-seconds"
        - "5.0"
        - "--max-connection-attempts"
        - "720"
      deploy:
        replicas: 10
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.role==client"
        restart_policy:
          condition: none
      depends_on:
      - server
...
"""


# noinspection DuplicatedCode
if __name__ == "__main__":

    tasks = ("square00",)
    models = ("naive", "empirical", "theoretical")
    workload_name = "EdgeDroidWiFi10"

    for task, model in itertools.product(tasks, models):
        ansible_ctx = AnsibleContext(base_dir=Path("ansible_env"))
        workload: WorkloadSpecification = WorkloadSpecification.from_dict(
            yaml.safe_load(
                generate_workload_def(
                    task=task, model=model, workload_name=workload_name
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
                PhysicalLayer(
                    hosts=hosts, radio_aps=sdr_aps, radio_stas=sdr_stas, switch=switch
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

            swarm.deploy_workload(
                specification=workload,
                attach_volume=storage.docker_vol_name,
                max_failed_health_checks=-1,
            )
