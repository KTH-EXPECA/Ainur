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

from importlib import resources
from ipaddress import IPv4Interface

import yaml

from ainur.hosts import Switch
from . import res

__all__ = ["get_aws_ami_id_for_region", "switch"]


def get_aws_ami_id_for_region(region: str) -> str:
    ami_file = resources.files(res).joinpath("offload-ami-ids.yaml")
    with resources.as_file(ami_file) as ami_path:
        return yaml.safe_load(ami_path)[region]


# the workload switch, no need to change this
# should eventually go in a config file.
switch = Switch(
    name="glorfindel",
    management_ip=IPv4Interface("192.168.0.2/16"),
    username="cisco",
    password="expeca",
)
