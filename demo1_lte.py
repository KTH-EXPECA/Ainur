#!/usr/bin/env python3
import contextlib
import os
import time
from contextlib import ExitStack
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from pathlib import Path
from typing import Iterator, Literal, Optional, Tuple

import ansible_runner
import click
import yaml
from frozendict import frozendict

from ainur.ansible import AnsibleContext
from ainur.cloud import CloudInstances
from ainur.hosts import (
    AinurCloudHostConfig,
    EthernetCfg,
    LocalAinurHost,
    WiFiCfg,
    WireSpec,
    IPRoute,
)
from ainur.networks import CompositeLayer3Network, LANLayer, VPNCloudMesh
from ainur.physical import PhysicalLayer
from ainur.swarm import DockerSwarm, WorkloadSpecification
from ainur_utils.hosts import EDGE_HOST, get_hosts
from ainur_utils.resources import switch, get_aws_ami_id_for_region

from autoran.oailte.epc import EvolvedPacketCore
from autoran.oailte.enodeb import ENodeB
from autoran.oailte.ue import LTEUE
from autoran.utils import DockerNetwork


# AWS_REGION = "eu-north-1"

CLOUD_HOST = AinurCloudHostConfig(
    management_ip=IPv4Interface("172.16.0.2/24"),
    workload_ip=IPv4Interface("172.16.1.2/24"),
    ansible_user="ubuntu",
)


def gen_vpn_gw_config(lte: bool = False) -> LocalAinurHost:
    return LocalAinurHost(
        management_ip=IPv4Interface("192.168.0.4/16"),
        ansible_user="expeca",
        ethernets=frozendict(
            {
                "eth0": EthernetCfg(
                    ip_address=IPv4Interface("10.4.0.3/24")
                    if lte
                    else IPv4Interface("10.0.1.0/16"),
                    routes=(
                        IPRoute(
                            to=IPv4Interface("10.5.0.0/24"),
                            via=IPv4Address("10.4.0.1"),
                        ),
                    ),
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


def gen_client_config(
    phy: Optional[Literal["ethernet", "wifi", "lte"]] = None
) -> LocalAinurHost:
    if (phy is None) or (phy == "ethernet"):
        return LocalAinurHost(
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
            wifis=frozendict(),
        )
    elif phy == "wifi":
        return LocalAinurHost(
            management_ip=IPv4Interface("192.168.3.0/16"),
            ansible_user="expeca",  # cloud instances have a different user
            ethernets=frozendict(),
            wifis=frozendict(
                wlan1=WiFiCfg(
                    ip_address=IPv4Interface("10.0.2.0/16"),
                    routes=(
                        # this route is necessary to reach the VPN to the cloud
                        IPRoute(
                            to=IPv4Interface("172.16.1.0/24"),
                            via=IPv4Address("10.0.1.0"),
                        ),
                    ),
                    mac="7c:10:c9:1c:3f:f0",
                    ssid="expeca_wlan_2",
                    password="EXPECA-WLAN",
                    hidden=True,
                )
            ),
        )
    elif phy == "lte":
        return LocalAinurHost(
            management_ip=IPv4Interface("192.168.3.0/16"),
            ansible_user="expeca",
            ethernets=frozendict(
                {
                    "eth0": EthernetCfg(
                        ip_address=IPv4Interface("10.5.0.2/24"),
                        routes=(
                            IPRoute(
                                to=IPv4Interface("10.4.0.0/24"),
                                via=IPv4Address("10.5.0.1"),
                            ),
                            IPRoute(
                                to=IPv4Interface("172.16.1.0/24"),
                                via=IPv4Address("10.5.0.1"),
                            ),
                        ),
                        mac="dc:a6:32:b4:d8:b5",
                        wire_spec=WireSpec(net_name="eth_net", switch_port=25),
                    ),
                }
            ),
            wifis=frozendict(),
        )
    else:
        raise RuntimeError(f"{phy=}")


def gen_cloudlet_config(lte: bool = False) -> LocalAinurHost:
    if lte:
        return LocalAinurHost(
            management_ip=IPv4Interface("192.168.1.2/16"),
            ansible_user="expeca",
            ethernets=frozendict(
                {
                    "enp4s0": EthernetCfg(
                        ip_address=IPv4Interface("10.4.0.2/24"),
                        routes=(
                            IPRoute(
                                to=IPv4Interface("10.5.0.0/24"),
                                via=IPv4Address("10.4.0.1"),
                            ),
                            IPRoute(
                                to=IPv4Interface("172.16.1.0/24"),
                                via=IPv4Address("10.4.0.3"),
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
        )
    else:
        return EDGE_HOST


LTE_BS = LocalAinurHost(
    management_ip=IPv4Interface("192.168.2.2/16"),
    ansible_user="expeca",
    ethernets=frozendict(
        {
            "enp5s0": EthernetCfg(
                ip_address=IPv4Interface("10.4.0.1/24"),
                routes=(
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"),
                        via=IPv4Address("10.4.0.3"),
                    ),
                ),
                mac="00:d8:61:c6:1c:e1",
                wire_spec=WireSpec(net_name="eth_net", switch_port=4),
            ),
        }
    ),
    wifis=frozendict(),
)

LTE_UE = LocalAinurHost(
    management_ip=IPv4Interface("192.168.2.1/16"),
    ansible_user="expeca",
    ethernets=frozendict(
        {
            "enp4s0": EthernetCfg(
                ip_address=IPv4Interface("10.5.0.1/24"),
                routes=(
                    IPRoute(
                        to=IPv4Interface("172.16.1.0/24"),
                        via=IPv4Address("10.4.0.1"),
                    ),
                ),
                mac="00:d8:61:c6:1b:27",
                wire_spec=WireSpec(net_name="eth_net", switch_port=3),
            ),
        }
    ),
    wifis=frozendict(),
)


def create_lte_epc(host: LocalAinurHost):
    # create EPC
    # EPC docker private network
    epc_private_network = DockerNetwork(
        host=str(host.management_ip.ip),
        network=IPv4Network("192.168.68.0/26"),
        name="prod-oai-private-net",
    )
    # EPC docker public network
    epc_public_network = DockerNetwork(
        host=str(host.management_ip.ip),
        network=IPv4Network("192.168.61.192/26"),
        name="prod-oai-public-net",
    )

    return EvolvedPacketCore(
        host=str(host.management_ip.ip),
        private_network=epc_private_network,
        public_network=epc_public_network,
    )


def create_epc_configs(epc: EvolvedPacketCore):

    # create hss config
    hss_config = {
        "TZ": "Europe/Paris",
        "REALM": "openairinterface.org",
        "HSS_FQDN": "hss.openairinterface.org",
        "PREFIX": "/openair-hss/etc",
        "cassandra_Server_IP": epc.cassandra_private_ip,
        "OP_KEY": "63bfa50ee6523365ff14c1f45f88737d",
        "LTE_K": "0c0a34601d4f07677303652c0462535b",
        "APN1": "oai.ipv4",
        "APN2": "oai2.ipv4",
        "FIRST_IMSI": "208960010000001",
        "NB_USERS": "5",
    }

    # create mme config
    mme_config = {
        "TZ": "Europe/Paris",
        "REALM": "openairinterface.org",
        "PREFIX": "/openair-mme/etc",
        "INSTANCE": 1,
        "PID_DIRECTORY": "/var/run",
        "HSS_IP_ADDR": epc.hss_public_ip,
        "HSS_HOSTNAME": "hss",
        "HSS_FQDN": "hss.openairinterface.org",
        "HSS_REALM": "openairinterface.org",
        "MCC": "208",
        "MNC": "96",
        "MME_GID": 32768,
        "MME_CODE": 3,
        "TAC_0": 1,
        "TAC_1": 2,
        "TAC_2": 3,
        "MME_FQDN": "mme.openairinterface.org",
        "MME_S6A_IP_ADDR": epc.mme_public_ip,
        "MME_INTERFACE_NAME_FOR_S1_MME": "eth0",
        "MME_IPV4_ADDRESS_FOR_S1_MME": epc.mme_public_ip,
        "MME_INTERFACE_NAME_FOR_S11": "eth0",
        "MME_IPV4_ADDRESS_FOR_S11": epc.mme_public_ip,
        "MME_INTERFACE_NAME_FOR_S10": "lo",
        "MME_IPV4_ADDRESS_FOR_S10": "127.0.0.10",
        "OUTPUT": "CONSOLE",
        "SGW_IPV4_ADDRESS_FOR_S11_0": epc.spgwc_public_ip,
        "PEER_MME_IPV4_ADDRESS_FOR_S10_0": "0.0.0.0",
        "PEER_MME_IPV4_ADDRESS_FOR_S10_1": "0.0.0.0",
        "MCC_SGW_0": "208",
        "MNC3_SGW_0": "096",
        "TAC_LB_SGW_0": "01",
        "TAC_HB_SGW_0": "00",
        "MCC_MME_0": "208",
        "MNC3_MME_0": "096",
        "TAC_LB_MME_0": "02",
        "TAC_HB_MME_0": "00",
        "MCC_MME_1": "208",
        "MNC3_MME_1": "096",
        "TAC_LB_MME_1": "03",
        "TAC_HB_MME_1": "00",
        "TAC_LB_SGW_TEST_0": "03",
        "TAC_HB_SGW_TEST_0": "00",
        "SGW_IPV4_ADDRESS_FOR_S11_TEST_0": "0.0.0.0",
    }

    # create spgwc config
    spgwc_config = {
        "TZ": "Europe/Paris",
        "SGW_INTERFACE_NAME_FOR_S11": "eth0",
        "PGW_INTERFACE_NAME_FOR_SX": "eth0",
        "DEFAULT_DNS_IPV4_ADDRESS": "192.168.18.129",
        "DEFAULT_DNS_SEC_IPV4_ADDRESS": "8.8.4.4",
        "PUSH_PROTOCOL_OPTION": "true",
        "APN_NI_1": "oai.ipv4",
        "APN_NI_2": "oai2.ipv4",
        "DEFAULT_APN_NI_1": "oai.ipv4",
        "UE_IP_ADDRESS_POOL_1": "12.1.1.2 - 12.1.1.254",
        "UE_IP_ADDRESS_POOL_2": "12.0.0.2 - 12.0.0.254",
        "MCC": "208",
        "MNC": "96",
        "MNC03": "096",
        "TAC": 1,
        "GW_ID": 1,
        "REALM": "openairinterface.org",
    }

    # create spgwu config
    spgwu_config = {
        "TZ": "Europe/Paris",
        "PID_DIRECTORY": "/var/run",
        "INSTANCE": 1,
        "SGW_INTERFACE_NAME_FOR_S1U_S12_S4_UP": "eth0",
        "PGW_INTERFACE_NAME_FOR_SGI": "eth0",
        "SGW_INTERFACE_NAME_FOR_SX": "eth0",
        "SPGWC0_IP_ADDRESS": epc.spgwc_public_ip,
        "NETWORK_UE_IP": "12.1.1.0/24",
        "NETWORK_UE_NAT_OPTION": "yes",
        "MCC": "208",
        "MNC": "96",
        "MNC03": "096",
        "TAC": 1,
        "GW_ID": 1,
        "REALM": "openairinterface.org",
    }

    # create epc routing config
    epc_routing_config = {
        "208960010000001": {
            "epc_tun_if": IPv4Interface("192.17.0.1/24"),
            "ue_tun_if": IPv4Interface("192.17.0.2/24"),
            "ue_ex_net": IPv4Network("10.5.0.0/24"),
        },
        "epc_ex_net_if": "enp5s0",
    }

    return {
        "hss_config": hss_config,
        "mme_config": mme_config,
        "spgwc_config": spgwc_config,
        "spgwu_config": spgwu_config,
        "epc_routing_config": epc_routing_config,
    }


def create_lte_enb(epc: EvolvedPacketCore, host: LocalAinurHost):
    return ENodeB(
        host=str(host.management_ip.ip),
        network=epc.docker_public_network,
        name="prod-oai-enb",
    )


def create_enb_config(enb: ENodeB, epc: EvolvedPacketCore):
    return {
        "mme_ip": epc.mme_public_ip,
        "spgwc_ip": epc.spgwc_public_ip,
        "USE_FDD_MONO": 1,
        "USE_B2XX": 1,
        "ENB_NAME": "eNB-Eurecom-LTEBox",
        "TAC": 1,
        "MCC": 208,
        "MNC": 96,
        "MNC_LENGTH": 2,
        "RRC_INACTIVITY_THRESHOLD": 30,
        "UTRA_BAND_ID": 7,
        "DL_FREQUENCY_IN_MHZ": 2680,
        "UL_FREQUENCY_OFFSET_IN_MHZ": 120,
        "NID_CELL": 0,
        "NB_PRB": 25,
        "ENABLE_MEASUREMENT_REPORTS": "yes",
        "MME_S1C_IP_ADDRESS": epc.mme_public_ip,
        "ENABLE_X2": "yes",
        "ENB_X2_IP_ADDRESS": enb.ip,
        "ENB_S1C_IF_NAME": "eth0",
        "ENB_S1C_IP_ADDRESS": enb.ip,
        "ENB_S1U_IF_NAME": "eth0",
        "ENB_S1U_IP_ADDRESS": enb.ip,
        "THREAD_PARALLEL_CONFIG": "PARALLEL_SINGLE_THREAD",
        "FLEXRAN_ENABLED": "no",
        "FLEXRAN_INTERFACE_NAME": "eth0",
        "FLEXRAN_IPV4_ADDRESS": "CI_FLEXRAN_CTL_IP_ADDR",
    }


def create_lte_ue(host: LocalAinurHost):
    # create ue config
    ue_config = {
        "PLMN_FULLNAME": "OpenAirInterface",
        "PLMN_SHORTNAME": "OAICN",
        "PLMN_CODE": "20896",
        "MCC": "208",
        "MNC": "96",
        "IMEI": "356113022094149",
        "MSIN": "0010000001",
        "USIM_API_K": "0c0a34601d4f07677303652c0462535b",
        "OPC": "ba05688178e398bedc100674071002cb",
        "MSISDN": "33611123456",
        "DL_FREQUENCY_IN_MHZ": 2680,
        "NB_PRB": 25,
        "RX_GAIN": 120,
        "TX_GAIN": 0,
        "MAX_POWER": 0,
    }

    # 172.17.0.0/24 network is reserved
    ue_routing_config = {
        "epc_tun_if": IPv4Interface("192.17.0.1/24"),
        "ue_tun_if": IPv4Interface("192.17.0.2/24"),
        "epc_ex_net": IPv4Network("10.4.0.0/24"),
        "ue_ex_net_if": "enp4s0",
    }

    return LTEUE(
        name="prod-oai-lte-ue",
        host=str(host.management_ip.ip),
        config=ue_config,
        routing_config=ue_routing_config,
    )


AP_PORT = 5
WORKLOAD_NAME = "EWDEMO1"
DURATION = "5m"

CLIENT_IMG = "expeca/demo_ew22_client"
SERVER_IMG = "expeca/demo_ew22_backend"


def generate_workload_def(
    offload: Literal["local", "edge", "cloud"],
    client: LocalAinurHost,
    cloudlet: LocalAinurHost,
    cloud: AinurCloudHostConfig,
):

    if offload == "local":
        backend_address = str(client.workload_ips[0])
    elif offload == "edge":
        backend_address = str(cloudlet.workload_ips[0])
    elif offload == "cloud":
        assert cloud is not None
        backend_address = str(cloud.workload_ip.ip)
    else:
        raise RuntimeError(offload)

    # language=yaml
    return f"""
---
name: {WORKLOAD_NAME}
author: "Manuel Olguín Muñoz, Vishnu N. Moothedath, S. Samie Mostafavi"
email: "molguin@kth.se"
version: "1.0a"
url: "expeca.proj.kth.se"
max_duration: "{DURATION}"
compose:
  version: "3.9"
  networks:
    swarmnet:
      driver: overlay
      attachable: true
      ipam:
        driver: default
        config:
        - subnet: 172.128.0.0/16
  services:
    server_service:
      image: {SERVER_IMG}
      hostname: server
      command: "--host 0.0.0.0 --port 1337"
      ports: 
      - "1337:1337/tcp"
      networks:
      - swarmnet
      deploy:
        replicas: 1
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.location=={offload}"
        restart_policy:
          condition: any
    client_service:
      image: {CLIENT_IMG}
      hostname: client
      ports:
      - "80:8080/tcp"
      networks:
      - swarmnet
      command: "--server-port 1337 {backend_address}"
      deploy:
        replicas: 1
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.role==client"
        restart_policy:
          condition: any
      depends_on:
      - server
...
"""


@contextlib.contextmanager
def build_physical_layer(
    phy: Literal["ethernet", "wifi", "lte"]
) -> Iterator[Tuple[PhysicalLayer, LocalAinurHost, LocalAinurHost, LocalAinurHost]]:
    client = gen_client_config(phy=phy)
    cloudlet = gen_cloudlet_config(lte=(phy == "lte"))
    vpn_gw = gen_vpn_gw_config(lte=(phy == "lte"))

    with ExitStack() as stack:
        if phy == "ethernet":
            physical: PhysicalLayer = stack.enter_context(
                PhysicalLayer(
                    hosts={"client": client, "cloudlet": cloudlet, "vpn_gw": vpn_gw},
                    radio_aps=[],
                    radio_stas=[],
                    switch=switch,
                )
            )
        else:
            physical: PhysicalLayer = stack.enter_context(
                PhysicalLayer(
                    hosts={},
                    radio_aps=[],
                    radio_stas=[],
                    switch=switch,
                )
            )
            if phy == "lte":
                # server/BS side
                physical._switch.make_vlan(
                    [
                        LTE_BS.ethernets["enp5s0"].wire_spec.switch_port,
                        cloudlet.ethernets["enp4s0"].wire_spec.switch_port,
                        vpn_gw.ethernets["eth0"].wire_spec.switch_port,
                    ],
                    name="lte_bs",
                )

                # client/UE side
                physical._switch.make_vlan(
                    [
                        LTE_UE.ethernets["enp4s0"].wire_spec.switch_port,
                        client.ethernets["eth0"].wire_spec.switch_port,
                    ],
                    name="lte_ue",
                )

                # create hosts dict
                physical._hosts = dict(
                    client=client,
                    elrond=cloudlet,
                    olwe=vpn_gw,
                    finarfin=LTE_BS,
                    fingolfin=LTE_UE,
                )
            else:
                # hack to make vlan including AP, elrond, and the VPN GW
                physical._switch.make_vlan(
                    [
                        AP_PORT,
                        cloudlet.ethernets["enp4s0"].wire_spec.switch_port,
                        vpn_gw.ethernets["eth0"].wire_spec.switch_port,
                    ],
                    name="edgedroid_vlan",
                )
                physical._hosts = dict(
                    client=client,
                    elrond=EDGE_HOST,
                    olwe=vpn_gw,
                )

        yield physical, client, cloudlet, vpn_gw


def local_deployment(ansible_ctx: AnsibleContext):
    client = gen_client_config()

    with ExitStack() as stack:
        phy: PhysicalLayer = stack.enter_context(
            PhysicalLayer(
                hosts={"client": client}, radio_aps=[], radio_stas=[], switch=switch
            )
        )

        lan: LANLayer = stack.enter_context(
            LANLayer(ansible_context=ansible_ctx, ansible_quiet=False)
        )
        lan.add_hosts(phy)

        # init swarm
        swarm: DockerSwarm = stack.enter_context(DockerSwarm())
        swarm.deploy_managers(hosts={client: dict(role="client", location="local")})
        # pull images
        swarm.pull_image(CLIENT_IMG)
        swarm.pull_image(SERVER_IMG)

        swarm.deploy_workload(
            specification=WorkloadSpecification.from_dict(
                yaml.safe_load(
                    generate_workload_def(
                        "local",
                        client=client,
                        cloudlet=client,
                        cloud=CLOUD_HOST,
                    )
                )
            ),
            max_failed_health_checks=-1,
        )


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
    type=click.Choice(["ethernet", "wifi", "lte"]),
    default="wifi",
    show_default=True,
    help="Phy layer to deploy.",
)
@click.option(
    "--region",
    type=str,
    default="eu-north-1",
    show_default=True,
    help="AWS Region to deploy to.",
)
def main(
    offload: Literal["local", "edge", "cloud"],
    phy: Literal["ethernet", "wifi", "lte"],
    region: str,
):
    ansible_ctx = AnsibleContext(base_dir=Path("ansible_env"))

    if offload == "local":
        local_deployment(ansible_ctx)
    else:
        # combines layer3 networks
        ip_layer = CompositeLayer3Network()

        # LAN
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
                wkld_local_net=IPv4Network("10.0.0.0/8"),
            )
        )

        with ExitStack() as stack:
            cloud: CloudInstances = stack.enter_context(
                CloudInstances(region=region),
            )

            phy_layer, client, cloudlet, vpn_gw = stack.enter_context(
                build_physical_layer(phy),
            )

            # init layer 3 connectivity
            ip_layer: CompositeLayer3Network = stack.enter_context(ip_layer)
            lan_layer.add_hosts(phy_layer)

            if offload == "cloud":
                # init and connect the cloud
                cloud.init_instances(
                    num_instances=1,
                    ami_id=get_aws_ami_id_for_region(region),
                )
                vpn_mesh.connect_cloud(
                    cloud_layer=cloud,
                    host_configs=[CLOUD_HOST],
                )

            if phy == "lte":
                # init lte network
                epc = stack.enter_context(create_lte_epc(LTE_BS))
                epc_configs = create_epc_configs(epc)
                enb = stack.enter_context(create_lte_enb(epc, LTE_BS))
                enb_config = create_enb_config(enb, epc)

                # input("Press any key to start lte epc...\n")

                epc.start(
                    hss_config=epc_configs["hss_config"],
                    mme_config=epc_configs["mme_config"],
                    spgwc_config=epc_configs["spgwc_config"],
                    spgwu_config=epc_configs["spgwu_config"],
                    routing_config=epc_configs["epc_routing_config"],
                )

                # input("Press any key to start lte enb...\n")

                enb.start(
                    config=enb_config,
                )

                wait_s = 20
                with click.progressbar(
                    length=wait_s,
                    label=f"Giving the LTE stack {wait_s} seconds to come online.",
                ) as bar:
                    for _ in bar:
                        time.sleep(1)

                lteue = stack.enter_context(create_lte_ue(LTE_UE))

                # hack to add route to UE to cloud through tunnel
                inventory = {
                    "all": {
                        "hosts": {
                            "LTE_UE": {
                                "ansible_host": LTE_UE.ansible_host,
                                "ansible_user": LTE_UE.ansible_user,
                                "ansible_become": True,
                            }
                        }
                    }
                }

                with ansible_ctx(inventory) as tmp_dir:
                    res = ansible_runner.run(
                        host_pattern="LTE_UE",
                        module="shell",
                        module_args="ip route add 172.16.1.0/24 dev tun0",
                        private_data_dir=str(tmp_dir),
                        quiet=False,
                        json_mode=False,
                    )

                    if res.status == "failed":
                        raise RuntimeError()
            # init swarm
            swarm: DockerSwarm = stack.enter_context(DockerSwarm())
            swarm.deploy_managers(
                hosts={
                    cloudlet: dict(
                        location="edge",
                        role="backend",
                    ),
                }
            ).deploy_workers(
                hosts={
                    client: dict(
                        role="client",
                        location="local",
                    ),
                }
            )

            if offload == "cloud":
                swarm.deploy_workers(
                    hosts={
                        CLOUD_HOST: dict(
                            role="backend",
                            location="cloud",
                        )
                    }
                )

            # pull images
            swarm.pull_image(CLIENT_IMG)
            swarm.pull_image(SERVER_IMG)

            # click.pause("Press any key to shut down.")

            swarm.deploy_workload(
                specification=WorkloadSpecification.from_dict(
                    yaml.safe_load(
                        generate_workload_def(
                            offload,
                            client=client,
                            cloudlet=cloudlet,
                            cloud=CLOUD_HOST,
                        )
                    )
                ),
                max_failed_health_checks=-1,
            )


if __name__ == "__main__":
    main()
