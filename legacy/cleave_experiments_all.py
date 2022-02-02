import abc
import itertools
import random
import time
from collections import deque
from contextlib import ExitStack
from dataclasses import dataclass, field
from ipaddress import IPv4Interface
from pathlib import Path
from typing import Any, Dict, Literal, Tuple

import yaml
from loguru import logger

from ainur import *
from pull_image import parallel_pull_image

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
        'workload-client-01': WorkloadHost(
            ansible_host='workload-client-01',
            management_ip=IPv4Interface('192.168.1.101/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:53:04',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=26),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='7c:10:c9:1c:3f:ea',
                ),
            },
        ),
        'workload-client-02': WorkloadHost(
            ansible_host='workload-client-02',
            management_ip=IPv4Interface('192.168.1.102/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:52:95',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=27),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='7c:10:c9:1c:3f:e8',
                ),
            },
        ),
        'workload-client-03': WorkloadHost(
            ansible_host='workload-client-03',
            management_ip=IPv4Interface('192.168.1.103/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:52:a1',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=28),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='7c:10:c9:1c:3e:04',
                ),
            },
        ),
        'workload-client-04': WorkloadHost(
            ansible_host='workload-client-04',
            management_ip=IPv4Interface('192.168.1.104/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:53:b8',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=29),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='fc:34:97:25:a1:9b',
                ),
            },
        ),
        'workload-client-05': WorkloadHost(
            ansible_host='workload-client-05',
            management_ip=IPv4Interface('192.168.1.105/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:07:fe:f2',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=30),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='7c:10:c9:1c:3e:a8',
                ),
            },
        ),
        'workload-client-06': WorkloadHost(
            ansible_host='workload-client-06',
            management_ip=IPv4Interface('192.168.1.106/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:53:f4',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=31),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='fc:34:97:25:a2:92',
                ),
            },
        ),
        'workload-client-07': WorkloadHost(
            ansible_host='workload-client-07',
            management_ip=IPv4Interface('192.168.1.107/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:52:83',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=32),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='24:4b:fe:b7:26:92',
                ),
            },
        ),
        'workload-client-08': WorkloadHost(
            ansible_host='workload-client-08',
            management_ip=IPv4Interface('192.168.1.108/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:54:12',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=33),
                ),
                'wlan0': WiFiInterface(
                    name='wlan0',
                    mac='f0:2f:74:63:5c:d9',
                ),
            },
        ),
        'workload-client-09': WorkloadHost(
            ansible_host='workload-client-09',
            management_ip=IPv4Interface('192.168.1.109/24'),
            interfaces={
                'eth0' : EthernetInterface(
                    name='eth0',
                    mac='dc:a6:32:bf:53:40',
                    switch_connection=SwitchConnection(name='glorfindel',
                                                       port=34),
                ),
                'wlan1': WiFiInterface(
                    name='wlan1',
                    mac='3c:7c:3f:a2:50:bd',
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
        'workload-client-01': {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.1/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-02': {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.2/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-03': {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.3/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-04': {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.4/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-05': {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.5/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-06': {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.6/16'),
                # phy=Wire(network='eth_net'),
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-07': {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.7/16'),
                # phy=Wire(network='eth_net')
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-08': {
            'wlan0': ConnectionSpec(
                ip=IPv4Interface('10.0.1.8/16'),
                # phy=Wire(network='eth_net')
                phy=WiFi(network='wlan_net', radio='native',
                         is_ap=False),
            ),
        },
        'workload-client-09': {
            'wlan1': ConnectionSpec(
                ip=IPv4Interface('10.0.1.9/16'),
                # phy=Wire(network='eth_net')
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
  workload-client-01:
    type: client
    arch: arm64
    conn: wifi
  workload-client-02:
    type: client
    arch: arm64
    conn: wifi
  workload-client-03:
    type: client
    arch: arm64
    conn: wifi
  workload-client-04:
    type: client
    arch: arm64
    conn: wifi
  workload-client-05:
    type: client
    arch: arm64
    conn: wifi
  workload-client-06:
   type: client
   arch: arm64
   conn: wifi
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


class ServiceConfig(abc.ABC):
    @abc.abstractmethod
    def as_service_dict(self) -> Dict[str, Any]:
        pass


@dataclass
class ExperimentConfig(ServiceConfig):
    name: str
    sampling_rate_hz: int
    id_suffix: str = ''
    image: str = 'molguin/cleave:cleave'
    delay_ms: int = 0
    replicas: int = 1
    add_constraints: Tuple[str, ...] = ()
    tick_rate_hz: int = 120
    local: bool = False
    service_cfg: str = field(init=False, default='', repr=False)
    service_dict: Dict[str, Any] = field(init=False, default_factory=dict,
                                         repr=False)

    def __post_init__(self):
        # suffix = '_local_' if self.local else '_'

        # self.name = f'cleave{suffix}' \
        #             f's{self.sampling_rate_hz:03d}Hz' \
        #             f'_t{self.tick_rate_hz:03d}Hz' \
        #             f'_d{self.delay_ms:03d}ms'

        delay_s = self.delay_ms / 1000.0
        plant_location = 'cloudlet' if self.local else 'client'
        add_consts = '\n      '.join([f'- "{c.strip()}"'
                                      for c in self.add_constraints])

        suffix = f'.{self.id_suffix}' if len(self.id_suffix) > 0 else ''
        suffix = '.{{.Task.Slot}}' + suffix

        # language=yaml
        self.service_cfg = f'''
controller_{self.name}:
  image: {self.image}
  hostname: "controller{suffix}"
  command:
    - run-controller
    - examples/inverted_pendulum/controller/config.py
  environment:
    PORT: "50000"
    NAME: "controller{suffix}"
    DELAY: "{delay_s:0.3f}"
  deploy:
    replicas: {self.replicas}
    placement:
      constraints:
      - "node.labels.type==cloudlet"
  volumes:
    - type: volume
      source: {self.name}
      target: /opt/controller_metrics/
      volume:
        nocopy: true
plant_{self.name}:
  image: {self.image}
  command:
    - run-plant
    - examples/inverted_pendulum/plant/config.py
  environment:
    NAME: "plant{suffix}"
    CONTROLLER_ADDRESS: "controller{suffix}"
    CONTROLLER_PORT: "50000"
    TICK_RATE: "{self.tick_rate_hz:d}"
    EMU_DURATION: "5m"
    FAIL_ANGLE_RAD: "-1"
    SAMPLE_RATE: "{self.sampling_rate_hz:d}"
  deploy:
    replicas: {self.replicas}
    placement:
      max_replicas_per_node: 1
      constraints:
      - "node.labels.type=={plant_location}"
      {add_consts}
    restart_policy:
      condition: on-failure
  volumes:
    - type: volume
      source: {self.name}
      target: /opt/plant_metrics/
      volume:
        nocopy: true
  depends_on:
  - controller_{self.name}
'''

        self.service_dict = yaml.safe_load(self.service_cfg)

    def as_service_dict(self) -> Dict[str, Any]:
        return dict(self.service_dict)


@dataclass
class LoadConfig(ServiceConfig):
    target_kbps: int
    packet_size_bytes: int
    client_hostname: str
    server_hostname: str
    pacing_interval_ms: int = 1
    name_suffix: str = ''
    transport: Literal['udp', 'tcp'] = 'udp'
    direction: Literal['downlink', 'uplink'] = 'downlink'
    image: str = 'taoyou/iperf3-alpine:latest'

    _service_dict: str = field(default='', init=False, repr=False)

    def __post_init__(self):
        # language=yaml
        _service_cfg = f'''
load_server{self.name_suffix}:
  image: {self.image}
  hostname: load_server{self.name_suffix}
  deploy:
    replicas: 1
    placement:
      constraints:
      - "node.hostname=={self.server_hostname}"
load_client{self.name_suffix}:
  image: {self.image}
  hostname: load_client{self.name_suffix}
  command:
  - -c
  - load_server{self.name_suffix}
  - -b{self.target_kbps:d}K
  - -t0
  - --pacing-timer
  - {self.pacing_interval_ms}K
  - -l{self.packet_size_bytes}
  {'- -R' if self.direction == 'downlink' else ''}
  {'- -u' if self.transport == 'udp' else ''}
  deploy:
    replicas: 1
    placement:
      constraints:
      - "node.hostname=={self.client_hostname}"
  depends_on:
  - load_server{self.name_suffix}
'''

        self._service_dict = yaml.safe_load(_service_cfg)

    def as_service_dict(self) -> Dict[str, Any]:
        return dict(self._service_dict)


if __name__ == '__main__':
    ansible_ctx = AnsibleContext(base_dir=Path('../ansible_env'))

    swarm_cfg = yaml.safe_load(swarm_config)

    managers = swarm_cfg['managers']
    workers = swarm_cfg['workers']

    conn_specs = workload_network_desc['connection_specs']

    load_clients = [
        f'workload-client-{i:02d}'
        for i in (6, 7, 8, 9)
    ]

    load_cfgs = [
        # LoadConfig(
        #     target_kbps=6500,
        #     packet_size_bytes=8000,
        #     client_hostname=c,
        #     server_hostname='elrond',
        #     direction='uplink',
        #     name_suffix=f'_{i:d}',
        #     pacing_interval_ms=41  # 24fps
        # )
        # for i, c in enumerate(load_clients)
    ]

    exp_configs = deque()
    # for rate, run in itertools.product((60,), (1,)):
    for rate, delay, run in itertools.product((40,), (50,), range(1, 31)):
        exp_configs.append(
            ExperimentConfig(
                name=f'cleave_s{rate:03d}Hz_t120Hz_d{delay:03d}ms',
                delay_ms=delay,
                sampling_rate_hz=rate,
                replicas=1,
                # add_constraints=tuple([f'node.hostname!={c}'
                #                        for c in load_clients]),
                id_suffix=f'run_{run:02d}'
            )
        )
    random.shuffle(exp_configs)

    # pull images
    docker_hosts = [str(host.management_ip.ip)
                    for _, host in inventory['hosts'].items()]

    # parallel_pull_image(docker_hosts, load_cfgs[0].image)
    parallel_pull_image(docker_hosts, exp_configs[0].image)

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
            LANLayer(
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

        # for exp_def in wifi_exps:
        base_def = yaml.safe_load(workload_def_template)

        for exp_config in exp_configs:
            services = {}
            for load_cfg in load_cfgs:
                services.update(load_cfg.as_service_dict())
            services.update(exp_config.as_service_dict())
            base_def['compose']['services'] = services

            workload: WorkloadSpecification = WorkloadSpecification \
                .from_dict(base_def)

            with ExperimentStorage(
                    storage_name=exp_config.name,
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
