from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Collection, Generator

import boto3
from mypy_boto3_ec2.service_resource import Instance


@contextmanager
def aws_instance_ctx(
        num_instances: int,
        ami_id: str = 'ami-05411ec0f7e9b0109',  # TODO: put somewhere else?
        instance_type: str = 't3.micro',
        key_name: str = 'ExPECA_AWS_Keys',
        security_groups: Collection[str] = ('sg-0170fa039ff0a56c4',),
        region: str = 'eu-north-1'
) -> Generator[Any, None, None]:
    ec2 = boto3.resource('ec2', region_name=region)
    # noinspection PyTypeChecker
    instances = ec2.create_instances(
        ImageId=ami_id,
        MinCount=num_instances,
        MaxCount=num_instances,
        InstanceType=instance_type,
        KeyName=key_name,
        SecurityGroupIds=list(security_groups)
    )

    # wait until instances are running and are accessible on port 22
    with ThreadPoolExecutor() as tpool:
        def _wait_for_instance(instance: Instance):
            # first wait until instance is "running" (does not mean the OS is
            # fully initialized though)
            instance.wait_until_running()

            # now, attempt to open a socket connection to port 22 to verify
            # that the instance is ready



