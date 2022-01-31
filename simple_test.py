from pathlib import Path

# from ainur import *
from ainur import AnsibleContext, NetworkLayer, PhysicalLayer
from ainur.hosts import *

switch = Switch(
    name='glorfindel',
    management_ip=IPv4Interface('192.168.0.2/16'),
    username='cisco',
    password='expeca',
)

sdr_network = SDRWiFiNetwork(
    ssid='expeca_wlan_1',
    channel=11,
    beacon_interval=100,
    ht_capable=True,
    access_point=SoftwareDefinedRadio(
        name='RFSOM-00002',
        management_ip=IPv4Interface('192.168.4.2/16'),
        mac='02:05:f7:80:0b:19',
        switch_port=42,
    ),
    stations=(
        SoftwareDefinedRadio(
            name='RFSOM-00001',
            management_ip=IPv4Interface('192.168.4.1/16'),
            mac='02:05:f7:80:0b:72',
            switch_port=41,
        ),
        SoftwareDefinedRadio(
            name='RFSOM-00003',
            management_ip=IPv4Interface('192.168.4.3/16'),
            mac='02:05:f7:80:02:c8',
            switch_port=43
        ),
    )
)

hosts = {
    'workload-client-00': AinurHost(
        management_ip=IPv4Interface('192.168.3.0/16'),
        ethernets=frozendict({
            'eth0': EthernetCfg(
                ip_address=IPv4Interface('10.0.1.0/16'),
                routes=(),
                mac='dc:a6:32:b4:d8:b5',
                wire_spec=WireSpec(
                    net_name='eth_net',
                    switch_port=25
                )
            ),
        }),
        wifis=frozendict()
    ),
    'workload-client-01': AinurHost(
        management_ip=IPv4Interface('192.168.3.1/16'),
        ethernets=frozendict({
            'eth0': EthernetCfg(
                ip_address=IPv4Interface('10.0.1.1/16'),
                routes=(),
                mac='dc:a6:32:bf:53:04',
                wire_spec=WireSpec(
                    net_name='eth_net',
                    switch_port=26
                )
            ),
        }),
        wifis=frozendict()
    ),
    'workload-client-02': AinurHost(
        management_ip=IPv4Interface('192.168.3.2/16'),
        ethernets=frozendict(),
        wifis=frozendict({
            'wlan0': WiFiCfg(
                mac='7c:10:c9:1c:3f:e8',
                ssid='expeca_wlan_1',
                ip_address=IPv4Interface('10.1.0.2/16'),
                routes=(),
            )
        })
    ),
    'elrond'            : AinurHost(
        management_ip=IPv4Interface('192.168.1.2/16'),
        ethernets=frozendict({
            'enp4s0': EthernetCfg(
                ip_address=IPv4Interface('10.1.0.1/16'),
                routes=(),
                mac='d8:47:32:a3:25:20',
                wire_spec=SDRWireSpec(
                    net_name='eth_net',
                    switch_port=2,
                    radio_port=42
                )
            )
        }),
        wifis=frozendict()
    ),
}

# noinspection DuplicatedCode
if __name__ == '__main__':
    ansible_ctx = AnsibleContext(base_dir=Path('ansible_env'))

    # Start phy layer
    with PhysicalLayer(hosts,
                       [sdr_network],
                       switch,
                       ansible_ctx,
                       ansible_quiet=True) as phy_layer:
        with NetworkLayer(
                layer2=phy_layer,
                ansible_context=ansible_ctx,
                ansible_quiet=True
        ) as workload_net:
            input('Running.')
