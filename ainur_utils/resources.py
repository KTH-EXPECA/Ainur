from importlib import resources
from ipaddress import IPv4Interface

import yaml

from ainur.hosts import Switch
from . import res

__all__ = ["get_aws_ami_id_for_region", "switch"]


def get_aws_ami_id_for_region(region: str) -> str:
    ami_file = resources.files(res).joinpath("offload-ami-ids.yaml")
    with resources.as_file(ami_file) as ami_path, ami_path.open("r") as fp:
        return yaml.safe_load(fp)[region]


# the workload switch, no need to change this
# should eventually go in a config file.
switch = Switch(
    name="glorfindel",
    management_ip=IPv4Interface("192.168.0.2/16"),
    username="cisco",
    password="expeca",
)
