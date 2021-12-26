import itertools
import time
from ipaddress import IPv4Interface
from pathlib import Path

import yaml
from loguru import logger

from ainur import *

inventory = {
    'hosts' : {
        'elrond'            : WorkloadHost(
            ansible_host='elrond',
            management_ip=IPv4Interface('192.168.1.4/24'),
            interfaces={
                'enp4s0': EthernetInterface(
                    name='enp4s0',
                    mac='d8:47:32:a3:25:20',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=2),
                )
            },
        ),
        'workload-client-00': WorkloadHost(
            ansible_host='workload-client-00',
            management_ip=IPv4Interface('192.168.1.100/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:b4:d8:b5',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=25),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='7c:10:c9:1c:3f:f0',
                ),
            },
        ),
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
# TODO: connection spec needs to be simplified to match phy!
workload_network_desc = {
    'subnetworks'     : {
        'wlan_net': WiFiNetwork(
            name='wlan_net',
            ssid='expeca_wlan_1',
            channel=11,
            beacon_interval=100,
            ht_capable=True,
        ),
        'eth_net' : WiredNetwork(
            name='eth_net',
        ),
    },
    'connection_specs': {
        'elrond'            : {
            'enp4s0': ConnectionSpec(
                ip=IPv4Interface('10.0.0.1/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='RFSOM-00002', is_ap=True)
            ),
        },
        'workload-client-00': {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.0/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
    }
}

# language=yaml
swarm_config = '''
---
managers:
  elrond:
    type: cloudlet
    arch: x86_64
workers:
  workload-client-00:
    type: client
    arch: arm64
    conn: wifi
...
'''

# language=yaml
workload_def_template = '''
---
name: cleave_20Hz_delay_{delay:01.3f}s
author: "Manuel Olguín Muñoz"
email: "molguin@kth.se"
version: "1.1a"
url: "expeca.proj.kth.se"
max_duration: "11m"
compose:
  version: "3.9"
  services:
    controller:
      image: molguin/cleave:cleave
      hostname: "controller.run_{run_idx:02d}"
      command:
        - run-controller
        - examples/inverted_pendulum/controller/config.py
      environment:
        PORT: "50000"
        NAME: "controller.run_{run_idx:02d}"
        DELAY: "{delay:0.3f}"
      deploy:
        replicas: 1
        placement:
          constraints:
          - "node.labels.type==cloudlet"
      volumes:
        - type: volume
          source: cleave_20Hz_delay_{delay:01.3f}s
          target: /opt/controller_metrics/
          volume:
            nocopy: true
    plant:
      image: molguin/cleave:cleave
      command:
        - run-plant
        - examples/inverted_pendulum/plant/config.py
      environment:
        NAME: "plant.run_{run_idx:02d}"
        CONTROLLER_ADDRESS: "controller.run_{run_idx:02d}"
        CONTROLLER_PORT: "50000"
        TICK_RATE: "100"
        EMU_DURATION: "10m"
        FAIL_ANGLE_RAD: "-1"
        SAMPLE_RATE: "20"
      deploy:
        replicas: 1
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.type==client"
        restart_policy:
          condition: on-failure
      volumes:
        - type: volume
          source: cleave_20Hz_delay_{delay:01.3f}s
          target: /opt/plant_metrics/
          volume:
            nocopy: true
      depends_on:
      - controller
...
'''

if __name__ == '__main__':
    ansible_ctx = AnsibleContext(base_dir=Path('./ansible_env'))
    # workload: WorkloadSpecification = \
    #     WorkloadSpecification.from_dict(yaml.safe_load(workload_def))

    swarm_cfg = yaml.safe_load(swarm_config)

    managers = swarm_cfg['managers']
    workers = swarm_cfg['workers']

    conn_specs = workload_network_desc['connection_specs']

    delays = (50, 100, 200, 400)

    # Phy, network, and Swarm layers are the same for all runs!
    with PhysicalLayer(inventory,
                       workload_network_desc,
                       ansible_ctx,
                       ansible_quiet=True) as phy_layer:
        host_ips = {}
        for host_name, host in phy_layer.items():
            conn_spec = conn_specs[host_name][host.workload_interface]
            host_ips[host_name] = conn_spec.ip

        with NetworkLayer(
                network_cfg=workload_network_desc['subnetworks'],
                host_ips=host_ips,
                layer2=phy_layer,
                ansible_context=ansible_ctx,
                ansible_quiet=True
        ) as workload_net:
            # TODO: connection check before swarm start! For now, just sleep
            #  for 30s to let all devices connect
            logger.warning('Sleeping for 30s to allow for all devices to '
                           'connect to network...')
            time.sleep(30)
            logger.warning('Continuing with workload deployment!')

            # TODO: fix dicts
            with DockerSwarm(
                    network=workload_net,
                    managers=dict(managers),
                    workers=dict(workers)
            ) as swarm:
                for delay, run in itertools.product(delays,
                                                    range(1, 11)):
                    logger.warning(
                        f'Delay {delay}s, run {run} out of 10.')
                    wkld_def = workload_def_template.format(
                        delay=delay,
                        run_idx=run
                    )
                    workload: WorkloadSpecification = WorkloadSpecification \
                        .from_dict(yaml.safe_load(wkld_def))

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
