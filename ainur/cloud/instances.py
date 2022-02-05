from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Collection, Iterable, List

import boto3
from loguru import logger
from mypy_boto3_ec2.service_resource import Instance

from .errors import CloudError


def _wait_instances_up(instances: Collection[Instance],
                       startup_timeout_s: int,
                       poll_port: int = 22):
    # wait until instances are running and are accessible on port 22
    with ThreadPoolExecutor() as tpool:
        def _wait_for_instance(inst: Instance):
            # first wait until instance is "running"
            # (does not mean the OS is fully initialized though)
            inst.wait_until_running()
            inst.reload()
            logger.debug(f'Instance {inst.instance_id} is running.')

            # now, attempt to open a socket connection to port to verify
            # that the instance is ready
            timeout = time.monotonic() + startup_timeout_s
            while time.monotonic() <= timeout:
                with socket.socket(socket.AF_INET,
                                   socket.SOCK_STREAM) as sock:
                    try:
                        sock.connect((inst.public_ip_address, poll_port))
                        # connected, return
                        logger.info(f'Instance {inst.instance_id} is '
                                    f'ready.')
                        return inst
                    except (TimeoutError, ConnectionRefusedError):
                        continue

            # could not connect
            # force the instance to terminate and raise an exception
            logger.warning(f'Time-out for instance {inst.instance_id}.')
            logger.warning(f'Aborting. Terminating instance '
                           f'{inst.instance_id}.')
            inst.terminate()  # this is asynchronous

            raise TimeoutError(f'Timed-out waiting for '
                               f'instance {inst.instance_id}.')

        logger.debug('Waiting for instances to finish booting...')
        spawned_instances = []
        try:
            for instance in tpool.map(_wait_for_instance, instances):
                spawned_instances.append(instance)
        except TimeoutError as e:
            tear_down_instances(spawned_instances)
            raise CloudError() from e
    return spawned_instances


def spawn_instances(num_instances: int,
                    key_name: str,
                    ami_id: str,
                    instance_type: str,
                    region: str,
                    security_group_ids: Collection[str] = (),
                    startup_timeout_s: int = 60 * 3,
                    poll_port: int = 22) -> List[Instance]:
    """
    Parameters
    ----------
    num_instances
        How many instances to deploy.
    key_name
        AWS key to use.
    ami_id
        The desired AMI for the instances.
    region
        AWS region on which to spawn instances.
    instance_type
        The desired EC2 instance type.
    security_group_ids
        Security groups to assign to the instances.
    startup_timeout_s
        Timeout for instance boot.
    poll_port
        Port to poll to detect instance up state.

    Returns
    -------
    self
        For chaining and using as a context manager.
    """

    logger.info(
        f'Deploying {num_instances} AWS compute instances of type '
        f'{instance_type}, on region {region}...')

    sec_groups = list(security_group_ids)
    logger.debug(f'Instance security groups: {sec_groups}')

    ec2 = boto3.resource('ec2', region_name=region)
    # noinspection PyTypeChecker
    instances = ec2.create_instances(
        ImageId=ami_id,
        MinCount=num_instances,
        MaxCount=num_instances,
        InstanceType=instance_type,
        KeyName=key_name,
        SecurityGroupIds=sec_groups
    )
    logger.debug('Instances created.')

    spawned_instances = _wait_instances_up(instances,
                                           startup_timeout_s=startup_timeout_s,
                                           poll_port=poll_port)

    logger.info('EC2 instances are booted and ready.')
    return spawned_instances


def tear_down_instances(instances: Iterable[Instance]) -> List[str]:
    with ThreadPoolExecutor() as tpool:
        def _shutdown_instance(inst: Instance) -> str:
            iid = inst.instance_id
            logger.debug(f'Terminating instance {inst.instance_id}...')
            inst.terminate()
            inst.wait_until_terminated()
            logger.warning(f'Instance {inst.instance_id} terminated.')
            return iid

        # list() forces the .map() statement to be evaluated immediately
        return list(tpool.map(_shutdown_instance, instances))
