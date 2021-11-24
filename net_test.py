from pathlib import Path

import yaml

from ainur import *
from ainur.swarm import WorkloadSpecification

# TODO: network config needs way of checking all interfaces actually exist!!

# language=yaml
net_swarm_config = '''
---
network:
  cidr: 10.0.0.0/16
  hosts:
    elrond:
      ansible_host: elrond.expeca
      management_ip: 192.168.1.4
      workload_nic: enp4s0
    workload-client-10:
      ansible_host: workload-client-10.expeca
      management_ip: 192.168.1.110
      workload_nic: eth0
    workload-client-11:
      ansible_host: workload-client-11.expeca
      management_ip: 192.168.1.111
      workload_nic: eth0
    workload-client-12:
      ansible_host: workload-client-12.expeca
      management_ip: 192.168.1.112
      workload_nic: eth0
swarm:
  managers:
    elrond:
      type: cloudlet
      arch: x86_64
  workers:
    workload-client-10:
      type: client
      arch: arm64
    workload-client-11:
      type: client
      arch: arm64
    workload-client-12:
      type: client
      arch: arm64
...
'''

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
    iperf3server:
      image: taoyou/iperf3-alpine:latest
      hostname: "iperf3server.{{.Task.Slot}}"
      deploy:
        replicas: 3
        placement:
          max_replicas_per_node: 3
          constraints:
          - "node.labels.type==cloudlet"
      command: "-s -1"
  
    iperf3client:
      image: taoyou/iperf3-alpine:latest
      privileged: yes
      deploy:
        replicas: 3
        placement:
          max_replicas_per_node: 1
          constraints:
          - "node.labels.type==client"
        restart_policy:
          condition: any
      command: "-c $${SERVER} -b 1M"
      environment:
        SERVER: "iperf3server.{{.Task.Slot}}"
      depends_on:
      - iperf3server
...
'''

if __name__ == '__main__':
    # quick test to verify network + swarm work

    ansible_ctx = AnsibleContext(base_dir=Path('./ansible_env'))

    workload = WorkloadSpecification.from_dict(yaml.safe_load(workload_def))

    net_swarm = yaml.safe_load(net_swarm_config)

    hosts = {
        name: DisconnectedWorkloadHost.from_dict(d)
        for name, d in net_swarm['network']['hosts'].items()
    }

    managers = net_swarm['swarm']['managers']
    workers = net_swarm['swarm']['workers']

    with WorkloadNetwork(
            cidr=net_swarm['network']['cidr'],
            hosts=hosts,
            ansible_context=ansible_ctx,
            ansible_quiet=True
    ) as workload_net:
        with DockerSwarm(
                network=workload_net,
                managers=managers,
                workers=workers
        ) as swarm:
            swarm.deploy_workload(
                specification=workload,
                health_check_poll_interval=10.0,
                max_failed_checks=-1
            )
