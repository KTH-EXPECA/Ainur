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

import os
from ipaddress import IPv4Address, IPv4Interface
from pathlib import Path

from ainur import AinurCloudHostConfig, AnsibleContext
from ainur.cloud.aws import CloudInstances
from ainur.networks.vpn import VPNCloudMesh

if __name__ == '__main__':
    with CloudInstances() as cloud:
        with VPNCloudMesh(
                gateway_ip=IPv4Address('130.237.53.70'),
                vpn_psk=os.getenv('vpn_psk'),
                ansible_ctx=AnsibleContext(base_dir=Path('../ansible_env')),
                ansible_quiet=False
        ) as vpn_mesh:
            cloud.init_instances(3)
            vpn_mesh.connect_cloud(
                cloud_layer=cloud,
                host_configs=[
                    AinurCloudHostConfig(
                        management_ip=IPv4Interface('172.16.0.2/24'),
                        workload_ip=IPv4Interface('172.16.1.2/24')
                    ),
                    AinurCloudHostConfig(
                        management_ip=IPv4Interface('172.16.0.3/24'),
                        workload_ip=IPv4Interface('172.16.1.3/24')
                    ),
                    AinurCloudHostConfig(
                        management_ip=IPv4Interface('172.16.0.4/24'),
                        workload_ip=IPv4Interface('172.16.1.4/24')
                    ),
                ]
            )

            for host_id, host in vpn_mesh.items():
                print(host_id, host.to_json())

            input('Press any key to tear down.')
