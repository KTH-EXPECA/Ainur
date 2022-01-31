from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Interface
from types import TracebackType
from typing import Any, Collection, Iterator, Mapping, Type, overload

import boto3
from loguru import logger
from mypy_boto3_ec2.service_resource import Instance

from ainur import CloudAinurHost


@dataclass(frozen=True, eq=True)
class EC2Host:
    instance_id: str
    public_ip: IPv4Address
    vpc_ip: IPv4Address

    @property
    def public_vpn_host_string(self, vpn_port: int = 3210) -> str:
        return f'{self.public_ip}:{vpn_port}'

    @property
    def vpc_vpn_host_string(self, vpn_port: int = 3210) -> str:
        return f'{self.vpc_ip}:{vpn_port}'

    def to_ainur_host(self,
                      management_ip: IPv4Interface,
                      workload_ip: IPv4Interface) -> CloudAinurHost:
        return CloudAinurHost(
            management_ip=management_ip,
            workload_ip=workload_ip,
            public_ip=self.public_ip,
            vpc_ip=self.vpc_ip
        )


class CloudError(Exception):
    pass


class CloudLayer(AbstractContextManager, Mapping[str, Instance]):
    def __init__(self,
                 num_instances: int,
                 ami_id: str = 'ami-05411ec0f7e9b0109',
                 instance_type: str = 't3.micro',
                 key_name: str = 'ExPECA_AWS_Keys',
                 security_groups: Collection[str] = ('sg-0170fa039ff0a56c4',),
                 region: str = 'eu-north-1',
                 startup_timeout_s: int = 60 * 3):
        """
        Context manager for AWS EC2 instances.

        Parameters
        ----------
        num_instances
            How many instances to deploy.
        ami_id
            The desired AMI for the instances.
        instance_type
            The desired EC2 instance type.
        key_name
            The name of the AWS keys to use.
        security_groups
            Security group IDs to attach to the instances.
        region
            On which region to create the instances.
        startup_timeout_s
            Timeout for instance boot.
        """

        self._num_instances = num_instances
        self._ami = ami_id
        self._ec2_type = instance_type
        self._key_name = key_name
        self._sec_groups = security_groups
        self._region = region
        self._startup_timeout = startup_timeout_s
        self._running_instances = {}

    def __enter__(self) -> CloudLayer:
        logger.warning(
            f'Deploying {self._num_instances} AWS compute instances of type '
            f'{self._ec2_type}...')

        ec2 = boto3.resource('ec2', region_name=self._region)
        # noinspection PyTypeChecker
        instances = ec2.create_instances(
            ImageId=self._ami,
            MinCount=self._num_instances,
            MaxCount=self._num_instances,
            InstanceType=self._ec2_type,
            KeyName=self._key_name,
            SecurityGroupIds=list(self._sec_groups)
        )
        logger.debug('Instances created.')

        # wait until instances are running and are accessible on port 22
        with ThreadPoolExecutor() as tpool:
            def _wait_for_instance(instance: Instance):
                # first wait until instance is "running"
                # (does not mean the OS is fully initialized though)
                instance.wait_until_running()
                instance.reload()
                logger.debug(f'Instance {instance.instance_id} is running.')

                # now, attempt to open a socket connection to port 22 to verify
                # that the instance is ready
                timeout = time.monotonic() + self._startup_timeout
                while time.monotonic() <= timeout:
                    with socket.socket(socket.AF_INET,
                                       socket.SOCK_STREAM) as sock:
                        try:
                            sock.connect((instance.public_ip_address, 22))
                            # connected, return
                            logger.info(f'Instance {instance.instance_id} is '
                                        f'ready.')
                            return instance
                        except (TimeoutError, ConnectionRefusedError):
                            continue

                # could not connect
                # force the instance to terminate and raise an exception
                logger.warning(f'Time-out for instance {instance.instance_id}.')
                logger.warning('Aborting.')
                instance.terminate()  # this is asynchronous

                raise TimeoutError(f'Timed-out waiting for '
                                   f'instance {instance.instance_id}.')

            logger.debug('Waiting for instances to finish booting...')

            try:
                for inst in tpool.map(_wait_for_instance, instances):
                    self._running_instances[inst.instance_id] = inst
            except TimeoutError as e:
                self.tear_down()
                raise CloudError() from e

        logger.info('All Cloud instances are booted and ready.')
        return self

    def __iter__(self) -> Iterator[str]:
        return iter(self._running_instances)

    def __getitem__(self, item: str) -> EC2Host:
        inst = self._running_instances[item]
        return EC2Host(
            instance_id=inst.instance_id,
            public_ip=IPv4Address(inst.public_ip_address),
            vpc_ip=IPv4Address(inst.private_ip_address)
        )

    def __len__(self) -> int:
        return len(self._running_instances)

    def __contains__(self, item: Any) -> bool:
        return item in self._running_instances

    def tear_down(self) -> None:
        # contextmanager shutting down, tear down and terminate all
        # the instances
        logger.warning('Shutting down AWS compute instances...')
        with ThreadPoolExecutor() as tpool:
            def _shutdown_instance(instance: Instance):
                logger.debug(f'Terminating instance {instance.instance_id}...')
                instance.terminate()
                instance.wait_until_terminated()
                logger.warning(f'Instance {instance.instance_id} terminated.')

            # list() forces the .map() statement to be evaluated immediately
            list(tpool.map(_shutdown_instance,
                           self._running_instances.values()))

    @overload
    def __exit__(self, exc_type: None, exc_val: None, exc_tb: None) -> None:
        ...

    @overload
    def __exit__(
            self,
            exc_type: Type[BaseException],
            exc_val: BaseException,
            exc_tb: TracebackType,
    ) -> None:
        ...

    def __exit__(
            self,
            exc_type: Type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
    ) -> None:
        self.tear_down()
