import os
from pathlib import Path

# from ainur import *
from ainur.hosts import *
from ainur.networks import *
from ainur.swarm import *
from ainur.swarm.storage import ExperimentStorage

with open('./offload-ami-ids.yaml', 'r') as fp:
    ami_ids = yaml.safe_load(fp)
region = 'eu-north-1'
# region = 'us-east-1'

switch = Switch(
    name='glorfindel',
    management_ip=IPv4Interface('192.168.0.2/16'),
    username='cisco',
    password='expeca',
)

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

hosts = {
    'workload-client-00': LocalAinurHost(
        management_ip=IPv4Interface('192.168.3.0/16'),
        ansible_user='expeca',
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
                routes=(
                    IPRoute(
                        to=IPv4Interface('172.16.1.0/24'),
                        via=IPv4Address('10.0.1.0')
                    ),
                ),
                mac='7c:10:c9:1c:3f:f0',
                ssid='expeca_wlan_1'
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
                routes=(
                    IPRoute(
                        to=IPv4Interface('172.16.1.0/24'),
                        via=IPv4Address('10.0.1.0')
                    ),
                ),
                mac='7c:10:c9:1c:3f:ea',
                ssid='expeca_wlan_1'
            )
        )
    ),
    # TODO: automatic way of configuring VPN gateway?
    'olwe'              : LocalAinurHost(
        management_ip=IPv4Interface('192.168.0.4/16'),
        ansible_user='expeca',
        ethernets=frozendict({
            'eth0': EthernetCfg(
                ip_address=IPv4Interface('10.0.1.0/16'),
                routes=(),
                mac='dc:a6:32:bf:54:1b',
                wire_spec=WireSpec(
                    net_name='eth_net',
                    switch_port=36,
                )
            )
        }),
        wifis=frozendict()
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

cloud_hosts = [
    AinurCloudHostConfig(
        management_ip=IPv4Interface('172.16.0.2/24'),
        workload_ip=IPv4Interface('172.16.1.2/24'),
        ansible_user='ubuntu',
    ),
    AinurCloudHostConfig(
        management_ip=IPv4Interface('172.16.0.3/24'),
        workload_ip=IPv4Interface('172.16.1.3/24'),
        ansible_user='ubuntu',
    ),
    AinurCloudHostConfig(
        management_ip=IPv4Interface('172.16.0.4/24'),
        workload_ip=IPv4Interface('172.16.1.4/24'),
        ansible_user='ubuntu',
    ),
]

# language=yaml
workload_def = '''
---
name: WorkloadExample
author: "Manuel Olguín Muñoz"
email: "molguin@kth.se"
version: "1.0a"
url: "expeca.proj.kth.se"
max_duration: "1m"
compose:
  version: "3.9"
  services:
    server:
      image: expeca/primeworkload:server
      hostname: "server.{{.Task.Slot}}"
      environment:
        PORT: 5000
      deploy:
        replicas: 4
        placement:
          max_replicas_per_node: 1  # 1 per cloud, 1 on elrond
          constraints:
          - "node.labels.role==backend"
  
    client:
      image: expeca/primeworkload:client
      environment:
        SERVER_ADDR: "server.{{.Task.Slot}}"
        SERVER_PORT: 5000
      deploy:
        replicas: 4
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.role==client"
        restart_policy:
          condition: on-failure
      depends_on:
      - server
...
'''

# noinspection DuplicatedCode
if __name__ == '__main__':
    ansible_ctx = AnsibleContext(base_dir=Path('ansible_env'))
    workload: WorkloadSpecification = \
        WorkloadSpecification.from_dict(yaml.safe_load(workload_def))

    # prepare everything
    cloud = CloudInstances(
        region=region
    )
    ip_layer = CompositeLayer3Network()

    lan_layer = ip_layer.add_network(
        LANLayer(ansible_context=ansible_ctx, ansible_quiet=False)
    )
    vpn_mesh = ip_layer.add_network(
        VPNCloudMesh(
            gateway_ip=IPv4Address('130.237.53.70'),
            vpn_psk=os.environ['vpn_psk'],
            ansible_ctx=ansible_ctx,
            ansible_quiet=False
        )
    )
    swarm = DockerSwarm()

    # TODO: rework Phy to also be "preparable"
    # TODO: same for experiment storage

    with ExitStack() as stack:
        cloud = stack.enter_context(cloud)

        # start phy layer
        phy_layer: PhysicalLayer = stack.enter_context(
            PhysicalLayer(hosts=hosts,
                          radio_aps=sdr_aps,
                          radio_stas=[],
                          switch=switch)
        )

        # init layer 3 connectivity
        ip_layer: CompositeLayer3Network = stack.enter_context(ip_layer)
        lan_layer.add_hosts(phy_layer)

        # TODO: rework Swarm config to something less manual. Maybe fold in
        #  configs into general host specification somehow??
        swarm: DockerSwarm = stack.enter_context(swarm)
        swarm.deploy_managers(hosts={hosts['elrond']: {}},
                              location='edge',
                              role='backend') \
            .deploy_workers(hosts={hosts['workload-client-00']: {},
                                   hosts['workload-client-01']: {}},
                            role='client')

        # start cloud instances
        cloud.init_instances(len(cloud_hosts), ami_id=ami_ids[region])
        vpn_mesh.connect_cloud(
            cloud_layer=cloud,
            host_configs=cloud_hosts
        )

        verify_wkld_net_connectivity(ip_layer)

        swarm.deploy_workers(hosts={host: {} for host in cloud_hosts},
                             role='backend', location='cloud')
        swarm.pull_image(image='expeca/primeworkload', tag='server')
        swarm.pull_image(image='expeca/primeworkload', tag='client')

        storage: ExperimentStorage = stack.enter_context(
            ExperimentStorage(
                storage_name='test-storage',
                storage_host=ManagedHost(
                    management_ip=IPv4Interface('192.168.1.1/16'),
                    ansible_user='expeca',
                ),
                network=ip_layer,
                ansible_ctx=ansible_ctx,
                ansible_quiet=False
            )
        )

        swarm.deploy_workload(
            specification=workload,
            attach_volume=storage.docker_vol_name,
            max_failed_health_checks=-1
        )
