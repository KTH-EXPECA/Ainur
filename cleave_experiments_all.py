import itertools
import random
import time
from collections import deque
from contextlib import ExitStack
from dataclasses import dataclass, field
from ipaddress import IPv4Interface
from pathlib import Path
from typing import Any, Deque, Dict

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
name: cleave_experiments
author: "Manuel Olguín Muñoz"
email: "molguin@kth.se"
version: "1.1a"
url: "expeca.proj.kth.se"
max_duration: "6m"
compose:
  version: "3.9"
  services: {}
...
'''


@dataclass
class ExperimentConfig:
    delay_ms: int
    sampling_rate_hz: int
    run_idx: int
    tick_rate_hz: int = 120
    local: bool = False
    name: str = field(init=False, default='')
    service_cfg: str = field(init=False, default='', repr=False)
    service_dict: Dict[str, Any] = field(init=False, default_factory=dict,
                                         repr=False)

    def __post_init__(self):
        suffix = '_local_' if self.local else '_'

        self.name = f'cleave{suffix}' \
                    f's{self.sampling_rate_hz:03d}Hz' \
                    f'_t{self.tick_rate_hz:03d}Hz' \
                    f'_d{self.delay_ms:03d}ms'

        delay_s = self.delay_ms / 1000.0
        plant_location = 'cloudlet' if self.local else 'client'

        # language=yaml
        self.service_cfg = f'''
controller_{self.name}:
  image: molguin/cleave:cleave
  hostname: "controller.run_{self.run_idx:02d}"
  command:
    - run-controller
    - examples/inverted_pendulum/controller/config.py
  environment:
    PORT: "50000"
    NAME: "controller.run_{self.run_idx:02d}"
  deploy:
    replicas: 1
    placement:
      constraints:
      - "node.labels.type==cloudlet"
  volumes:
    - type: volume
      source: {self.name}
      target: /opt/controller_metrics/
      volume:
        nocopy: true
proxy_{self.name}:
  image: expeca/awsproxy:latest
  hostname: "proxy.run_{self.run_idx:02d}"
  environment:
    SERVERIP: "controller.run_{self.run_idx:02d}"
    {"DELAY: " + str(self.delay_ms) if self.delay_ms > 0 else ""}
  cap_add:
    - NET_ADMIN
  deploy:
    replicas: 1
    placement:
      constraints:
      - "node.labels.type==cloudlet"
  depends_on:
    - controller_{self.name}
plant_{self.name}:
  image: molguin/cleave:cleave
  command:
    - run-plant
    - examples/inverted_pendulum/plant/config.py
  environment:
    NAME: "plant.run_{self.run_idx:02d}"
    CONTROLLER_ADDRESS: "proxy.run_{self.run_idx:02d}"
    CONTROLLER_PORT: "50000"
    TICK_RATE: "{self.tick_rate_hz:d}"
    EMU_DURATION: "5m"
    FAIL_ANGLE_RAD: "-1"
    SAMPLE_RATE: "{self.sampling_rate_hz:d}"
  deploy:
    replicas: 1
    placement:
      max_replicas_per_node: 1
      constraints:
      - "node.labels.type=={plant_location}"
    restart_policy:
      condition: on-failure
  volumes:
    - type: volume
      source: {self.name}
      target: /opt/plant_metrics/
      volume:
        nocopy: true
  depends_on:
    - proxy_{self.name}
    - controller_{self.name}
'''

        self.service_dict = yaml.safe_load(self.service_cfg)

    def as_service_dict(self) -> Dict[str, Any]:
        return self.service_dict


if __name__ == '__main__':
    ansible_ctx = AnsibleContext(base_dir=Path('./ansible_env'))

    swarm_cfg = yaml.safe_load(swarm_config)

    managers = swarm_cfg['managers']
    workers = swarm_cfg['workers']

    conn_specs = workload_network_desc['connection_specs']

    # experiments over wifi
    # delays = 0 25 50 100
    # srates = 10 20 40 60
    # combs = 16
    # 6 mins/each -> 16 hours
    # 4 mins/each -> ~11 hours

    # 60Hz x 25ms x 30
    # 40Hz x 50ms x 30

    combs_60hz = list(itertools.product(
        range(1, 31),
        (25,),
        (60,)
    ))

    combs_40hz = list(itertools.product(
        range(1, 31),
        (50,),
        (40,)
    ))

    wifi_exps: Deque[ExperimentConfig] = deque()
    wifi_combs = deque()
    wifi_combs.extend(combs_40hz)
    wifi_combs.extend(combs_60hz)

    assert len(wifi_combs) == 60

    random.shuffle(wifi_combs)
    for i, d, s in wifi_combs:
        wifi_exps.append(
            ExperimentConfig(
                delay_ms=d,
                sampling_rate_hz=s,
                run_idx=i,
                local=False
            )
        )

    with ExitStack() as stack:
        phy_layer = stack.enter_context(
            PhysicalLayer(inventory,
                          workload_network_desc,
                          ansible_ctx,
                          ansible_quiet=True)
        )

        host_ips = {}
        for host_name, host in phy_layer.items():
            conn_spec = conn_specs[host_name][host.workload_interface]
            host_ips[host_name] = conn_spec.ip

        workload_net = stack.enter_context(
            NetworkLayer(
                network_cfg=workload_network_desc['subnetworks'],
                host_ips=host_ips,
                layer2=phy_layer,
                ansible_context=ansible_ctx,
                ansible_quiet=True
            )
        )
        logger.warning('Sleeping for 30s to allow for all devices to '
                       'connect to network...')
        time.sleep(30)
        logger.warning('Continuing with workload deployment!')

        swarm = stack.enter_context(
            DockerSwarm(
                network=workload_net,
                managers=dict(managers),
                workers=dict(workers)
            )
        )

        for exp_def in wifi_exps:
            base_def = yaml.safe_load(workload_def_template)
            base_def['compose']['services'] = exp_def.as_service_dict()

            workload: WorkloadSpecification = WorkloadSpecification \
                .from_dict(base_def)

            logger.warning(
                f'Running: {exp_def}'
            )

            with ExperimentStorage(
                    storage_name=exp_def.name,
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
