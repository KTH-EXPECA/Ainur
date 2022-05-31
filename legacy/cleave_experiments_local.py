#  Copyright (c) 2022 KTH Royal Institute of Technology, Sweden,
#  and the ExPECA Research Group (PI: Prof. James Gross).
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import itertools
import random
import time
from contextlib import ExitStack
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
    }
}

# language=yaml
swarm_config = '''
---
managers:
  elrond:
    type: cloudlet
    arch: x86_64
workers: {}
...
'''

# language=yaml
workload_def_template = '''
---
name: cleave_local_s{srate:03d}Hz_t{trate:03d}Hz_d{delay_ms:03d}ms
author: "Manuel Olguín Muñoz"
email: "molguin@kth.se"
version: "1.1a"
url: "expeca.proj.kth.se"
max_duration: "6m"
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
        DELAY: "{delay_s:0.3f}"
      deploy:
        replicas: 1
        placement:
          constraints:
          - "node.labels.type==cloudlet"
      volumes:
        - type: volume
          source: cleave_local_s{srate:03d}Hz_t{trate:03d}Hz_d{delay_ms:03d}ms
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
        TICK_RATE: "{trate:d}"
        EMU_DURATION: "5m"
        FAIL_ANGLE_RAD: "-1"
        SAMPLE_RATE: "{srate:d}"
      deploy:
        replicas: 1
        placement:
          constraints:
          - "node.labels.type==cloudlet"
        restart_policy:
          condition: on-failure
      volumes:
        - type: volume
          source: cleave_local_s{srate:03d}Hz_t{trate:03d}Hz_d{delay_ms:03d}ms
          target: /opt/plant_metrics/
          volume:
            nocopy: true
      depends_on:
      - controller
...
'''

if __name__ == '__main__':
    ansible_ctx = AnsibleContext(base_dir=Path('../ansible_env'))

    swarm_cfg = yaml.safe_load(swarm_config)

    managers = swarm_cfg['managers']
    workers = swarm_cfg['workers']

    conn_specs = workload_network_desc['connection_specs']

    # sampling_rates = (5, 10, 20, 40)
    delays = (0.0,)
    # batch sampling rates to get some results before others
    sampling_rate_batches = ((40, 60), (120,))

    tick_rate = 120
    num_runs = 10

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

        for sampling_rates in sampling_rate_batches:
            logger.warning(f'Sampling rate batch: {sampling_rates}Hz')

            # shuffle delay/sampling rate combinations
            delay_sampling_combs = list(itertools.product(delays,
                                                          sampling_rates))
            random.shuffle(delay_sampling_combs)

            for run, (delay, srate) in itertools.product(range(1, num_runs + 1),
                                                         delay_sampling_combs):
                logger.warning(
                    f'Delay {delay}s, sampling rate {srate}Hz, '
                    f'run {run} out of {num_runs}.'
                )
                wkld_def = workload_def_template.format(
                    delay_ms=int(delay * 1000),
                    delay_s=delay,
                    run_idx=run,
                    trate=tick_rate,
                    srate=srate
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
