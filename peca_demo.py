import os
from pathlib import Path

import click

# from ainur import *
from ainur.hosts import *
from ainur.networks import *
from ainur.swarm import *
from ainur.swarm.storage import ExperimentStorage

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
]


# noinspection DuplicatedCode
@click.command()
@click.option('-r', '--region', type=str, default='local', show_default=True)
@click.option('-d', '--duration', type=str, default='30s', show_default=True)
@click.option('-t', '--plant-tick-rate', type=int, default=100,
              show_default=True)
@click.option('-s', '--plant-sample-rate', type=int, default=100,
              show_default=True)
def run_peca_demo(region: str,
                  duration: str,
                  plant_tick_rate: int,
                  plant_sample_rate: int) -> None:
    """
    Run demo.

    Parameters
    ----------

    region
        AWS region to run on, or 'local' to run locally.

    duration
        Emulation duration as a timeparse string.

    plant_tick_rate
        Tick rate in Hz.

    plant_sample_rate
        Sampling rate in Hz.
    """

    workload_name = f'CLEAVE-{region}'
    image = 'molguin/cleave'
    tag = 'cleave'

    # language=yaml
    workload_def = f'''
---
name: {workload_name}
author: "Manuel Olguín Muñoz"
email: "molguin@kth.se"
version: "1.0a"
url: "expeca.proj.kth.se"
max_duration: "1m"
compose:
  version: "3.9"
  services:
    controller:
      image: {image}:{tag}
      hostname: "controller"
      command:
        - -vvvvv
        - run-controller
        - examples/inverted_pendulum/controller/config.py
      environment:
        PORT: "50000"
        NAME: "controller"
      deploy:
        replicas: 1
        placement:
          constraints:
          - "node.labels.role==controller"
          - "node.labels.location=={region}"
      volumes:
        - type: volume
          source: {workload_name}
          target: /opt/controller_metrics/
          volume:
            nocopy: true
  
    plant:
      image: {image}:{tag}
      command:
        - -vvvvv
        - run-plant
        - examples/inverted_pendulum/plant/config.py
      environment:
        NAME: "plant"
        CONTROLLER_ADDRESS: "controller"
        CONTROLLER_PORT: "50000"
        TICK_RATE: "{plant_tick_rate:d}"
        EMU_DURATION: "{duration}"
        FAIL_ANGLE_RAD: "-1"
        SAMPLE_RATE: "{plant_sample_rate:d}"
      deploy:
        replicas: 1
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.role==plant"
        restart_policy:
          condition: on-failure
      volumes:
        - type: volume
          source: {workload_name}
          target: /opt/plant_metrics/
          volume:
            nocopy: true
      depends_on:
      - controller
...
'''

    with open('./offload-ami-ids.yaml', 'r') as fp:
        ami_ids = yaml.safe_load(fp)

    assert region in ami_ids or region == 'local'

    ansible_ctx = AnsibleContext(base_dir=Path('ansible_env'))
    workload: WorkloadSpecification = \
        WorkloadSpecification.from_dict(yaml.safe_load(workload_def))

    # prepare everything
    if region != 'local':
        cloud = CloudInstances(region=region)

    ip_layer = CompositeLayer3Network()

    lan_layer = ip_layer.add_network(
        LANLayer(ansible_context=ansible_ctx, ansible_quiet=False)
    )

    if region != 'local':
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
        if region != 'local':
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
                              role='controller',
                              location='local') \
            .deploy_workers(hosts={hosts['workload-client-00']: {}},
                            role='plant',
                            location='local')

        if region != 'local':
            # start cloud instances
            cloud.init_instances(len(cloud_hosts), ami_id=ami_ids[region])
            vpn_mesh.connect_cloud(
                cloud_layer=cloud,
                host_configs=cloud_hosts
            )
            swarm.deploy_workers(hosts={host: {} for host in cloud_hosts},
                                 role='controller',
                                 location=region)

        logger.info('Cluster configured and ready to deploy workload.')
        logger.debug(f'Backend configuration: {region}')
        logger.info('Waiting for confirmation to continue...')
        if click.confirm('Continue?', default=None):
            logger.info('Deploying workload...')

            swarm.pull_image(image=image, tag=tag)

            storage: ExperimentStorage = stack.enter_context(
                ExperimentStorage(
                    storage_name=workload_name,
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


if __name__ == '__main__':
    run_peca_demo()
