import os
from pathlib import Path

# from ainur import *
from ainur.hosts import *
from ainur.networks import *
from ainur.swarm import *
from ainur.swarm.storage import ExperimentStorage

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
    APSoftwareDefinedRadio(
        name='RFSOM-00002',
        management_ip=IPv4Interface('172.16.2.12/24'),
        mac='02:05:f7:80:0b:19',
        switch_port=42,
        ssid='expeca_wlan_1',
        net_name='eth_net',
        channel=11,
        beacon_interval=100,
        ht_capable=True
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
    'workload-client-00': LocalAinurHost(
        management_ip=IPv4Interface('192.168.3.0/16'),
        ansible_user='expeca',  # cloud instances have a different user
        # ethernets=frozendict({
        #     'eth0': EthernetCfg(
        #         ip_address=IPv4Interface('10.0.2.0/16'),
        #         routes=(
        #             IPRoute(
        #                 to=IPv4Interface('172.16.1.0/24'),
        #                 via=IPv4Address('10.0.1.0')
        #             ),
        #         ),
        #         mac='dc:a6:32:b4:d8:b5',
        #         wire_spec=WireSpec(
        #             net_name='eth_net',
        #             switch_port=25
        #         )
        #     ),
        # }),
        # wifis=frozendict(),
        ethernets=frozendict(),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface('10.0.2.0/16'),
                routes=(),
                mac='7c:10:c9:1c:3f:f0',
                ssid='expeca_wlan_1'  # SDR wifi ssid
            )
        )
    ),
    'workload-client-01': LocalAinurHost(
        management_ip=IPv4Interface('192.168.3.1/16'),
        ansible_user='expeca',
        # ethernets=frozendict({
        #     'eth0': EthernetCfg(
        #         ip_address=IPv4Interface('10.0.2.1/16'),
        #         routes=(  # VPN route
        #             IPRoute(
        #                 to=IPv4Interface('172.16.1.0/24'),
        #                 via=IPv4Address('10.0.1.0')
        #             ),
        #         ),
        #         mac='dc:a6:32:bf:53:04',
        #         wire_spec=WireSpec(
        #             net_name='eth_net',
        #             switch_port=26
        #         )
        #     ),
        # }),
        # wifis=frozendict(),
        ethernets=frozendict(),
        wifis=frozendict(
            wlan1=WiFiCfg(
                ip_address=IPv4Interface('10.0.2.1/16'),
                routes=(),
                mac='7c:10:c9:1c:3f:ea',
                ssid='expeca_wlan_1'
            )
        )
    ),
    'elrond'            : LocalAinurHost(
        management_ip=IPv4Interface('192.168.1.2/16'),
        ansible_user='expeca',
        ethernets=frozendict({
            'enp4s0': EthernetCfg(
                ip_address=IPv4Interface('10.0.1.1/16'),
                routes=(  # VPN route
                    IPRoute(
                        to=IPv4Interface('172.16.1.0/24'),
                        via=IPv4Address('10.0.1.0')
                    ),
                ),
                mac='d8:47:32:a3:25:20',
                wire_spec=WireSpec(
                    net_name='eth_net',
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

        input("Press any key to stop...\n")
