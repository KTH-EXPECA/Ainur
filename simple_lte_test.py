import os
from pathlib import Path

# from ainur import *
from ainur.hosts import *
from ainur.networks import *
from ainur.swarm import *
from ainur.swarm.storage import ExperimentStorage

from autoran.oailte.epc import EvolvedPacketCore
from autoran.oailte.enodeb import ENodeB
from autoran.oailte.ue  import LTEUE
from autoran.utils import DockerNetwork

# the workload switch, no need to change this
# should eventually go in a config file.
switch = Switch(
    name='glorfindel',
    management_ip=IPv4Interface('192.168.0.2/16'),
    username='cisco',
    password='expeca',
)

# SDR access point configurations for this workload scenario
# note that SDRs are no longer associated to hosts, but rather to the network
# as a whole.
# The switch connects the port of the sdr to the rest of the network (
# according to the net_name parameter) so that devices connected by wifi and
# devices on the wire can talk to each other (and so devices connected by
# wifi can reach the cloud! this is important).
sdr_aps = [
#     APSoftwareDefinedRadio(
#         name='RFSOM-00002',
#         management_ip=IPv4Interface('172.16.2.12/24'),
#         mac='02:05:f7:80:0b:19',
#         switch_port=42,
#         ssid='expeca_wlan_1',
#         net_name='eth_net',
#         channel=11,
#         beacon_interval=100,
#         ht_capable=True
#     )
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

# create EPC networks
# EPC private network
epc_private_network = DockerNetwork(
        host='finarfin',
        network=IPv4Network('192.168.68.0/26'),
        name='prod-oai-private-net'
)
# EPC public network
epc_public_network = DockerNetwork(
        host='finarfin',
        network=IPv4Network('192.168.61.192/26'),
        name='prod-oai-public-net'
)
# create EPC
epc = EvolvedPacketCore(
        host='finarfin',
        private_network=epc_private_network,
        public_network=epc_public_network,
)

# create hss config
hss_config={
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
mme_config={
    "TZ": "Europe/Paris",
    "REALM": "openairinterface.org",
    "PREFIX": "/openair-mme/etc",
    "INSTANCE": 1,
    "PID_DIRECTORY": "/var/run",
    "HSS_IP_ADDR": epc.hss_public_ip,
    "HSS_HOSTNAME": 'hss',
    "HSS_FQDN": "hss.openairinterface.org",
    "HSS_REALM": "openairinterface.org",
    'MCC': '208',
    'MNC': '96',
    'MME_GID': 32768,
    'MME_CODE': 3,
    'TAC_0': 1,
    'TAC_1': 2,
    'TAC_2': 3,
    'MME_FQDN': 'mme.openairinterface.org',
    'MME_S6A_IP_ADDR': epc.mme_public_ip,
    'MME_INTERFACE_NAME_FOR_S1_MME': 'eth0',
    'MME_IPV4_ADDRESS_FOR_S1_MME': epc.mme_public_ip,
    'MME_INTERFACE_NAME_FOR_S11': 'eth0',
    'MME_IPV4_ADDRESS_FOR_S11': epc.mme_public_ip,
    'MME_INTERFACE_NAME_FOR_S10': 'lo',
    'MME_IPV4_ADDRESS_FOR_S10': '127.0.0.10',
    'OUTPUT': 'CONSOLE',
    'SGW_IPV4_ADDRESS_FOR_S11_0': epc.spgwc_public_ip,
    'PEER_MME_IPV4_ADDRESS_FOR_S10_0': '0.0.0.0',
    'PEER_MME_IPV4_ADDRESS_FOR_S10_1': '0.0.0.0',
    'MCC_SGW_0': '208',
    'MNC3_SGW_0': '096',
    'TAC_LB_SGW_0': '01',
    'TAC_HB_SGW_0': '00',
    'MCC_MME_0': '208',
    'MNC3_MME_0': '096',
    'TAC_LB_MME_0': '02',
    'TAC_HB_MME_0': '00',
    'MCC_MME_1': '208',
    'MNC3_MME_1': '096',
    'TAC_LB_MME_1': '03',
    'TAC_HB_MME_1': '00',
    'TAC_LB_SGW_TEST_0': '03',
    'TAC_HB_SGW_TEST_0': '00',
    'SGW_IPV4_ADDRESS_FOR_S11_TEST_0': '0.0.0.0',
}

# create spgwc config
spgwc_config = {
    'TZ': 'Europe/Paris',
    'SGW_INTERFACE_NAME_FOR_S11': 'eth0',
    'PGW_INTERFACE_NAME_FOR_SX': 'eth0',
    'DEFAULT_DNS_IPV4_ADDRESS': '192.168.18.129',
    'DEFAULT_DNS_SEC_IPV4_ADDRESS': '8.8.4.4',
    'PUSH_PROTOCOL_OPTION': 'true',
    'APN_NI_1': 'oai.ipv4',
    'APN_NI_2': 'oai2.ipv4',
    'DEFAULT_APN_NI_1': 'oai.ipv4',
    'UE_IP_ADDRESS_POOL_1': '12.1.1.2 - 12.1.1.254',
    'UE_IP_ADDRESS_POOL_2': '12.0.0.2 - 12.0.0.254',
    'MCC': '208',
    'MNC': '96',
    'MNC03': '096',
    'TAC': 1,
    'GW_ID': 1,
    'REALM': 'openairinterface.org',
}

# create spgwu config
spgwu_config = {
    'TZ': 'Europe/Paris',
    'PID_DIRECTORY': '/var/run',
    'INSTANCE': 1,
    'SGW_INTERFACE_NAME_FOR_S1U_S12_S4_UP': 'eth0',
    'PGW_INTERFACE_NAME_FOR_SGI': 'eth0',
    'SGW_INTERFACE_NAME_FOR_SX': 'eth0',
    'SPGWC0_IP_ADDRESS': epc.spgwc_public_ip,
    'NETWORK_UE_IP': '12.1.1.0/24',
    'NETWORK_UE_NAT_OPTION': 'yes',
    'MCC': '208',
    'MNC': '96',
    'MNC03': '096',
    'TAC': 1,
    'GW_ID': 1,
    'REALM': 'openairinterface.org',
}

# create epc routing config
epc_routing_config = {
    '208960010000001':{
        'epc_tun_if' : IPv4Interface('192.17.0.1/24'),
        'ue_tun_if' : IPv4Interface('192.17.0.2/24'),
        'ue_ex_net' : IPv4Network('10.5.0.0/24'),
    },
    'epc_ex_net_if' : 'enp5s0',
}

# create ENodeB
enb = ENodeB(
    host='finarfin',
    network=epc_public_network,
    name='prod-oai-enb',
)

enb_config = {
    "mme_ip":epc.mme_public_ip,
    "spgwc_ip":epc.spgwc_public_ip,
    "USE_FDD_MONO": 1,
    "USE_B2XX": 1,
    'ENB_NAME':'eNB-Eurecom-LTEBox',
    'TAC':1,
    'MCC':208,
    'MNC':96,
    'MNC_LENGTH':2,
    'RRC_INACTIVITY_THRESHOLD':30,
    'UTRA_BAND_ID':7,
    'DL_FREQUENCY_IN_MHZ':2680,
    'UL_FREQUENCY_OFFSET_IN_MHZ':120,
    'NID_CELL':0,
    'NB_PRB':25,
    'ENABLE_MEASUREMENT_REPORTS':'yes',
    'MME_S1C_IP_ADDRESS':epc.mme_public_ip,
    'ENABLE_X2':'yes',
    'ENB_X2_IP_ADDRESS':enb.ip,
    'ENB_S1C_IF_NAME':'eth0',
    'ENB_S1C_IP_ADDRESS':enb.ip,
    'ENB_S1U_IF_NAME':'eth0',
    'ENB_S1U_IP_ADDRESS':enb.ip,
    'THREAD_PARALLEL_CONFIG':'PARALLEL_SINGLE_THREAD',
    'FLEXRAN_ENABLED':'no',
    'FLEXRAN_INTERFACE_NAME':'eth0',
    'FLEXRAN_IPV4_ADDRESS':'CI_FLEXRAN_CTL_IP_ADDR',
}


# create ue config
ue_config = {
    "PLMN_FULLNAME":"OpenAirInterface",
    "PLMN_SHORTNAME":"OAICN",
    "PLMN_CODE":"20896",
    "MCC":"208",
    "MNC":"96",
    "IMEI":"356113022094149",
    "MSIN":"0010000001",
    "USIM_API_K":"0c0a34601d4f07677303652c0462535b",
    "OPC":"ba05688178e398bedc100674071002cb",
    "MSISDN":"33611123456",
    'DL_FREQUENCY_IN_MHZ':2680,
    'NB_PRB':25,
    'RX_GAIN':120,
    'TX_GAIN':0,
    'MAX_POWER':0,
}

# 172.17.0.0/24 network is reserved
ue_routing_config = {
    'epc_tun_if' : IPv4Interface('192.17.0.1/24'),
    'ue_tun_if' : IPv4Interface('192.17.0.2/24'),
    'epc_ex_net' : IPv4Network('10.4.0.0/24'),
    'ue_ex_net_if': 'enp4s0',
}


# hosts is a mapping from host name to a LocalAinurHost object
# note that the system determines how to connect devices using the ethernets
# and wifis dict.
# also note that if a device has more than one workload interface, ONLY ONE
# WILL BE USED (and it will be selected arbitrarily!)
hosts = {
    'workload-client-00': LocalAinurHost(
        management_ip=IPv4Interface('192.168.3.0/16'),
        ansible_user='expeca',
        ethernets=frozendict({
            'eth0': EthernetCfg(
                ip_address=IPv4Interface('10.5.0.2/24'),
                routes=(
                    IPRoute(
                        to=IPv4Interface('10.4.0.0/24'),
                        via=IPv4Address('10.5.0.1')
                    ),
                ),
                mac='dc:a6:32:b4:d8:b5',
                wire_spec=WireSpec(
                    net_name='eth_net_ue',
                    switch_port=25
                )
            ),
        }),
        wifis=frozendict(),
        # ethernets=frozendict(),
        # wifis=frozendict(
        #     wlan1=WiFiCfg(
        #         ip_address=IPv4Interface('10.0.0.0/24'),
        #         routes=(),
        #         mac='7c:10:c9:1c:3f:f0',
        #         ssid='expeca_wlan_1'  # SDR wifi ssid
        #     )
    ),
    'fingolfin': LocalAinurHost(
        management_ip=IPv4Interface('192.168.2.1/16'),
        ansible_user='expeca',
        ethernets=frozendict({
            'enp4s0': EthernetCfg(
                ip_address=IPv4Interface('10.5.0.1/24'),
                routes=(),
                mac='00:d8:61:c6:1b:27',
                wire_spec=WireSpec(
                    net_name='eth_net_ue',
                    switch_port=3
                ),
            ),
        }),
        wifis=frozendict(),
    ),
    'finarfin': LocalAinurHost(
        management_ip=IPv4Interface('192.168.2.2/16'),
        ansible_user='expeca',
        ethernets=frozendict({
            'enp5s0': EthernetCfg(
                ip_address=IPv4Interface('10.4.0.1/24'),
                routes=(),
                mac='00:d8:61:c6:1c:e1',
                wire_spec=WireSpec(
                    net_name='eth_net_epc',
                    switch_port=4
                )
            ),
        }),
        wifis=frozendict(),
    ),
    'elrond'            : LocalAinurHost(
        management_ip=IPv4Interface('192.168.1.2/16'),
        ansible_user='expeca',
        ethernets=frozendict({
            'enp4s0': EthernetCfg(
                ip_address=IPv4Interface('10.4.0.2/24'),
                routes=(
                    IPRoute(
                        to=IPv4Interface('10.5.0.0/24'),
                        via=IPv4Address('10.4.0.1')
                    ),
                ),
                mac='d8:47:32:a3:25:20',
                wire_spec=WireSpec(
                    net_name='eth_net_epc',
                    switch_port=2,
                )
            )
        }),
        wifis=frozendict()
    ),
}


# noinspection DuplicatedCode
if __name__ == '__main__':
    ansible_ctx = AnsibleContext(base_dir=Path('ansible_env'))

    # this object merges and arbitrary number of VPN and local networks. it
    # can be left here if the VPN is removed.
    ip_layer = CompositeLayer3Network()

    lan_layer = ip_layer.add_network(
        LANLayer(ansible_context=ansible_ctx, ansible_quiet=False)
    )
    
    # TODO: rework Phy to also be "preparable"
    # TODO: same for experiment storage

    with ExitStack() as stack:

        # start phy layer
        phy_layer: PhysicalLayer = stack.enter_context(
            PhysicalLayer(hosts=hosts,
                          radio_aps=sdr_aps,
                          radio_stas=sdr_stas,
                          switch=switch)
        )

        # init layer 3 connectivity
        ip_layer: CompositeLayer3Network = stack.enter_context(ip_layer)
        lan_layer.add_hosts(phy_layer)

        
        input("Press any key to start lte epc...\n")

        epc.start(
            hss_config=hss_config,
            mme_config=mme_config,
            spgwc_config=spgwc_config,
            spgwu_config=spgwu_config,
            routing_config=epc_routing_config,
        )


        input("Press any key to start lte enb...\n")
        
        enb.start(
            config=enb_config,
        )

        input("Press any key to start lte ue...\n")

        lteue = LTEUE(
            name='prod-oai-lte-ue',
            host='fingolfin',
            config=ue_config,
            routing_config=ue_routing_config,
        )

        input("Press any key to stop...\n")

        lteue.__del__()
        enb.__del__()
        epc.__del__()

