from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import Collection, Generator, Tuple

import boto3
from loguru import logger
from mypy_boto3_ec2.service_resource import Instance


@dataclass(frozen=True, eq=True)
class EC2Host:
    instance_id: str
    public_ip: IPv4Address
    vpc_ip: IPv4Address


@contextmanager
def aws_instance_ctx(
        num_instances: int,
        ami_id: str = 'ami-05411ec0f7e9b0109',  # TODO: put somewhere else?
        instance_type: str = 't3.micro',
        key_name: str = 'ExPECA_AWS_Keys',
        security_groups: Collection[str] = ('sg-0170fa039ff0a56c4',),
        region: str = 'eu-north-1',
        startup_timeout_s: int = 60 * 3
) -> Generator[Tuple[EC2Host, ...], None, None]:
    logger.warning(f'Deploying {num_instances} AWS compute instances of type '
                   f'{instance_type}...')

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
    logger.debug('Instances created.')

    # wait until instances are running and are accessible on port 22
    with ThreadPoolExecutor() as tpool:
        def _wait_for_instance(instance: Instance):
            # first wait until instance is "running" (does not mean the OS is
            # fully initialized though)
            instance.wait_until_running()
            instance.reload()
            logger.debug(f'Instance {instance.instance_id} is running.')

            # now, attempt to open a socket connection to port 22 to verify
            # that the instance is ready
            timeout = time.monotonic() + startup_timeout_s
            while time.monotonic() <= timeout:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    try:
                        sock.connect((instance.public_ip_address, 22))
                        # connected, return
                        logger.info(f'Instance {instance.instance_id} is '
                                    f'ready.')
                        return instance
                    except (TimeoutError, ConnectionRefusedError):
                        continue

            # could not connect
            raise TimeoutError(f'Timed-out waiting for '
                               f'instance {instance.instance_id}.')

        logger.debug('Waiting for instances to finish booting...')
        instances = list(tpool.map(_wait_for_instance, instances))

    # at this point, instances are up and running
    yield tuple([EC2Host(
        instance_id=inst.instance_id,
        public_ip=IPv4Address(inst.public_ip_address),
        vpc_ip=IPv4Address(inst.private_ip_address)
    ) for inst in instances])

    # contextmanager shutting down, tear down and terminate all the instances
    logger.warning('Shutting down AWS compute instances...')
    with ThreadPoolExecutor() as tpool:
        def _shutdown_instance(instance: Instance):
            logger.debug(f'Terminating instance {instance.instance_id}...')
            instance.terminate()
            instance.wait_until_terminated()
            logger.warning(f'Instance {instance.instance_id} terminated.')

        # list() forces the .map() statement to be evaluated immediately
        list(tpool.map(_shutdown_instance, instances))


if __name__ == '__main__':
    with aws_instance_ctx(10) as insts:
        for i in insts:
            print(i)

        input('Press any key to shut down.')

