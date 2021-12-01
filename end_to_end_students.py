from ipaddress import IPv4Interface
from pathlib import Path

import yaml

from ainur import *

inventory = {
    'hosts' : {
        'workload-client-04': WorkloadHost(
            ansible_host='workload-client-04',
            management_ip=IPv4Interface('192.168.1.104/24'),
            interfaces={'eth0': EthernetInterface(
                name='eth0',
                mac='dc:a6:32:bf:53:b8',
                switch_connection=SwitchConnection(name='glorfindel',
                                                   port=29),
            ),
            },
        ),
        'workload-client-05': WorkloadHost(
            ansible_host='workload-client-05',
            management_ip=IPv4Interface('192.168.1.105/24'),
            interfaces={'eth0': EthernetInterface(
                name='eth0',
                mac='dc:a6:32:07:fe:f2',
                switch_connection=SwitchConnection(name='glorfindel',
                                                   port=30),
            ),
            },
        ),
        'workload-client-06': WorkloadHost(
            ansible_host='workload-client-06',
            management_ip=IPv4Interface('192.168.1.106/24'),
            interfaces={'eth0': EthernetInterface(
                name='eth0',
                mac='dc:a6:32:bf:53:f4',
                switch_connection=SwitchConnection(name='glorfindel',
                                                   port=31),
            ),
            },
        ),
        'workload-client-07': WorkloadHost(
            ansible_host='workload-client-07',
            management_ip=IPv4Interface('192.168.1.107/24'),
            interfaces={'eth0': EthernetInterface(
                name='eth0',
                mac='dc:a6:32:bf:52:83',
                switch_connection=SwitchConnection(name='glorfindel',
                                                   port=32),
            ),
            },
        ),
        'workload-client-08': WorkloadHost(
            ansible_host='workload-client-08',
            management_ip=IPv4Interface('192.168.1.108/24'),
            interfaces={'eth0': EthernetInterface(
                name='eth0',
                mac='dc:a6:32:bf:54:12',
                switch_connection=SwitchConnection(name='glorfindel',
                                                   port=33),
            ),
                # 'wlan0'       : WiFiInterface(
                #     name='wlan0',
                #     mac='f0:2f:74:63:5c:d9',
                # ),
            },
        ),
        'workload-client-09': WorkloadHost(
            ansible_host='workload-client-09',
            management_ip=IPv4Interface('192.168.1.109/24'),
            interfaces={'eth0': EthernetInterface(
                name='eth0',
                mac='dc:a6:32:bf:53:40',
                switch_connection=SwitchConnection(name='glorfindel',
                                                   port=34),
            ),
            },
        ),
        'elrond'            : WorkloadHost(
            ansible_host='elrond',
            management_ip=IPv4Interface('192.168.1.4/24'),
            interfaces={'enp4s0': EthernetInterface(
                name='enp4s0',
                mac='d8:47:32:a3:25:20',
                switch_connection=SwitchConnection(name='glorfindel',
                                                   port=2),
            )
            },
        )
    },
    'radios': {
        'RFSOM-00001': SoftwareDefinedRadio(
            name='RFSOM-00001',
            mac='02:05:f7:80:0b:72',
            management_ip=IPv4Interface('192.168.1.61/24'),
            switch_connection=SwitchConnection(name='glorfindel', port=41)
        ),
        'RFSOM-00002': SoftwareDefinedRadio(
            name='RFSOM-00002',
            mac='02:05:f7:80:0b:19',
            management_ip=IPv4Interface('192.168.1.62/24'),
            switch_connection=SwitchConnection(name='glorfindel', port=42)
        ),
        'RFSOM-00003': SoftwareDefinedRadio(
            name='RFSOM-00003',
            mac='02:05:f7:80:02:c8',
            management_ip=IPv4Interface('192.168.1.63/24'),
            switch_connection=SwitchConnection(name='glorfindel', port=43)
        ),
    },
    'switch': Switch(
        name='glorfindel',
        management_ip='192.168.1.5/24',
        username='cisco',
        password='expeca',
    ),
}

# TODO: connection spec should not include IP addresses, as this mixes the
#  layers.
workload_network_desc = {
    'subnetworks'     : {
        # 'wlan_net': WiFiNetwork(
        #     name='wlan_net',
        #     ssid='expeca_wlan_1',
        #     channel=11,
        #     beacon_interval=100,
        #     ht_capable=True,
        # ),
        'eth_net' : WiredNetwork(
            name='eth_net',
        ),
    },
    'connection_specs': {
        'workload-client-07': {
            'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.0.7/16'),
                phy=Wire(network='eth_net')
                # phy=WiFi(network='wlan_net', radio='RFSOM-00002', is_ap=True),
            ),
        },
        'workload-client-08': {
            'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.0.8/16'),
                phy=Wire(network='eth_net')
                # phy=WiFi(network='wlan_net', radio='native', is_ap=False),
            ),
        },
        'workload-client-09': {
            'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.0.9/16'),
                phy=Wire(network='eth_net')
                # phy=WiFi(network='wlan_net', radio='RFSOM-00001', is_ap=False),
            ),
        },
        'workload-client-04': {
            'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.1.4/16'),
                phy=Wire(network='eth_net'),
            ),
        },
        'workload-client-05': {
            'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.1.5/16'),
                phy=Wire(network='eth_net'),
            ),
        },
        'workload-client-06': {
            'eth0': ConnectionSpec(
                ip=IPv4Interface('10.0.1.6/16'),
                phy=Wire(network='eth_net'),
            ),
        },
        'elrond'            : {
            'enp4s0': ConnectionSpec(
                ip=IPv4Interface('10.0.0.1/16'),
                phy=Wire(network='eth_net'),
            ),
        },
    }
}

# language=yaml
workload_def = '''
---
name: MOSNtest1
author: "Mosn2444"
email: "sandiv@kth.se"
version: "1.0a"
url: "expeca.proj.kth.se"
max_duration: "7m"
compose:
  version: "3.9"
  services:
    controller:
      image: mosn2444/final_cleave:version1.1
      hostname: "controller.{{.Task.Slot}}"
      command:
        - run-controller
        - examples/inverted_pendulum/controller/config.py
      environment:
        PORT: "50000"
        NAME: "controller.{{.Task.Slot}}"
      deploy:
        replicas: 3
        placement:
          constraints:
          - "node.labels.type==cloudlet"
      volumes:
        - type: volume
          source: MOSNtest1
          target: /opt/controller_metrics/
          volume:
            nocopy: true
    plant:
      image: mosn2444/final_cleave:version1.1
      command:
        - run-plant
        - examples/inverted_pendulum/plant/config.py
      environment:
        NAME: "plant.{{.Task.Slot}}"
        CONTROLLER_ADDRESS: "controller.{{.Task.Slot}}"
        CONTROLLER_PORT: "50000"
        TICK_RATE: "100"
        EMU_DURATION: "5m"
        FAIL_ANGLE_RAD: "1"
      deploy:
        replicas: 3
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.type==client"
        restart_policy:
          condition: on-failure
      volumes:
        - type: volume
          source: MOSNtest1
          target: /opt/plant_metrics/
          volume:
            nocopy: true
      depends_on:
      - controller

...
'''

# language=yaml
swarm_config = '''
---
managers:
  elrond:
    type: cloudlet
    arch: x86_64
workers:
  workload-client-04:
    type: client
    arch: arm64
    conn: eth
  workload-client-05:
    type: client
    arch: arm64
    conn: eth
  workload-client-06:
    type: client
    arch: arm64
    conn: eth
  workload-client-07:
    type: client
    arch: arm64
    conn: wifi
  workload-client-08:
    type: client
    arch: arm64
    conn: wifi
  workload-client-09:
    type: client
    arch: arm64
    conn: wifi
...
'''

if __name__ == '__main__':
    ansible_ctx = AnsibleContext(base_dir=Path('./ansible_env'))
    workload: WorkloadSpecification = \
        WorkloadSpecification.from_dict(yaml.safe_load(workload_def))

    swarm_cfg = yaml.safe_load(swarm_config)

    managers = swarm_cfg['managers']
    workers = swarm_cfg['workers']

    conn_specs = workload_network_desc['connection_specs']

    # Start phy layer
    with PhysicalLayer(inventory,
                       workload_network_desc,
                       ansible_ctx,
                       ansible_quiet=True) as phy_layer:
        host_ips = {}
        for host_name, host in phy_layer.items():
            conn_spec = conn_specs[host_name][host.workload_interface]
            host_ips[host_name] = conn_spec.ip

        with NetworkLayer(
                host_ips=host_ips,
                layer2=phy_layer,
                ansible_context=ansible_ctx,
                ansible_quiet=True
        ) as workload_net:
            with DockerSwarm(
                    network=workload_net,
                    managers=managers,
                    workers=workers
            ) as swarm:
                with ExperimentStorage(
                        storage_name=workload.name,
                        storage_host=WorkloadHost(
                            ansible_host='galadriel.expeca',
                            management_ip=IPv4Interface('192.168.1.2'),
                            interfaces={}
                        ),
                        network=workload_net,
                        ansible_ctx=ansible_ctx
                ) as storage:
                    swarm.deploy_workload(
                        specification=workload,
                        attach_volume=storage.docker_vol_name,
                        health_check_poll_interval=10.0,
                        complete_threshold=3,
                        max_failed_health_checks=-1
                    )
