from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Interface
from types import TracebackType
from typing import Any, Collection, Dict, Iterator, Mapping, Set, Type, overload

import boto3
from loguru import logger
from mypy_boto3_ec2.service_resource import Instance, SecurityGroup, Vpc
from mypy_boto3_ec2.type_defs import IpPermissionTypeDef

from ..hosts import AinurCloudHost


@dataclass(frozen=True, eq=True)
class EC2Host:
    instance_id: str
    public_ip: IPv4Address
    vpc_ip: IPv4Address

    def to_ainur_host(self,
                      management_ip: IPv4Interface,
                      workload_ip: IPv4Interface) -> AinurCloudHost:
        return AinurCloudHost(
            management_ip=management_ip,
            workload_ip=workload_ip,
            public_ip=self.public_ip,
            vpc_ip=self.vpc_ip
        )


class CloudError(Exception):
    pass


class CloudInstances(AbstractContextManager, Mapping[str, EC2Host]):
    """
    Context manager for AWS EC2 instances.
    """

    # old default sec group: sg-0170fa039ff0a56c4

    def __init__(self,
                 region: str = 'eu-north-1',
                 key_name: str = 'ExPECA_AWS_Keys',
                 default_sec_groups: Collection[str] = ()):
        """
        Parameters
        ----------
        region:
            AWS region on which to deploy instances.
        key_name
            The name of the AWS keys to use.
        default_sec_groups
            Default, mandatory security groups to attach instances to.
        """

        self._running_instances: Dict[str, Instance] = {}
        self._region = region
        self._sec_groups: Set[str] = set(default_sec_groups)
        self._ephemeral_sec_groups: Set[SecurityGroup] = set()
        self._key_name = key_name

    def __str__(self):
        return f'CloudLayer(region: {self._region}, ' \
               f'running instances: {len(self._running_instances)})'

    def create_sec_group(self,
                         name: str,
                         desc: str,
                         ingress_rules: Collection[IpPermissionTypeDef] = (),
                         egress_rules: Collection[IpPermissionTypeDef] = (),
                         ssh_access: bool = True,
                         ephemeral: bool = True,
                         attach_to_instances: bool = True) -> str:

        logger.info(f'Creating security group {name} ({desc}) in region '
                    f'{self._region}.')
        logger.debug(f'Ingress rules:\n{ingress_rules}')
        logger.debug(f'Egress rules:\n{egress_rules}')

        ec2 = boto3.resource('ec2', region_name=self._region)
        vpc: Vpc = list(ec2.vpcs.all())[0]

        ingress_rules = list(ingress_rules)
        egress_rules = list(egress_rules)

        # allow traffic to flow freely outwards
        egress_rules.append(
            IpPermissionTypeDef(IpProtocol='-1')
        )

        try:
            sec_group = ec2.create_security_group(
                Description=desc,
                GroupName=name,
                VpcId=vpc.vpc_id
            )

            # allow traffic to flow freely within sec group
            sec_group.authorize_ingress(
                SourceSecurityGroupName=sec_group.group_id
            )

            if ssh_access:
                # allow ssh access
                sec_group.authorize_ingress(
                    CidrIp='0.0.0.0/0',
                    FromPort=22,
                    ToPort=22,
                    IpProtocol='tcp',
                )

            # other ingress and egress rules
            if len(ingress_rules) > 0:
                sec_group.authorize_ingress(IpPermissions=ingress_rules)
            sec_group.authorize_egress(IpPermissions=egress_rules)

            if ephemeral:
                self._ephemeral_sec_groups.add(sec_group)

            logger.info(f'Create security group {name} '
                        f'with id {sec_group.group_id} '
                        f'in region {self._region}')

            if attach_to_instances:
                logger.info(f'Attaching security group {name} to running '
                            f'instances.')
                # immediately attach the security group to all running instances
                for iid, instance in self._running_instances.items():
                    logger.debug(f'Attaching security group {name} to '
                                 f'instance {iid}...')
                    instance.reload()
                    security_groups = set([g['GroupId']
                                           for g in instance.security_groups])
                    security_groups.add(sec_group.group_id)

                    instance.modify_attribute(
                        Attribute='groupSet',
                        Groups=list(security_groups)
                    )

                    logger.debug(f'Updated security groups for instance {iid}:'
                                 f'{security_groups}')

            return sec_group.group_id
        except Exception as e:
            logger.error(f'Could not create/configure security group {name}.')
            raise CloudError(
                f'Failed to create security group {name} ({desc}) in '
                f'region {self._region}.'
            ) from e

    def clear_ephemeral_sec_groups(self) -> None:
        logger.warning('Deleting ephemeral security groups '
                       f'in region {self._region}...')
        for sec_group in self._ephemeral_sec_groups:
            logger.debug(f'Deleting security group {sec_group.group_name} '
                         f'({sec_group.description}, region {self._region})')
            sec_group.delete()

        logger.warning('Deleted all ephemeral security groups '
                       f'in region {self._region}.')
        self._ephemeral_sec_groups.clear()

    def init_instances(self,
                       num_instances: int,
                       ami_id: str = 'ami-05411ec0f7e9b0109',
                       instance_type: str = 't3.micro',
                       additional_sec_groups: Collection[str] = (),
                       startup_timeout_s: int = 60 * 3):
        """
        Parameters
        ----------
        num_instances
            How many instances to deploy.
        ami_id
            The desired AMI for the instances.
        instance_type
            The desired EC2 instance type.
        additional_sec_groups
            Additional security groups to which attach the instances.
        startup_timeout_s
            Timeout for instance boot.

        Returns
        -------
        self
            For chaining and using as a context manager.
        """

        logger.warning(
            f'Deploying {num_instances} AWS compute instances of type '
            f'{instance_type}, on region {self._region}...')

        sec_groups = list(self._sec_groups.union(additional_sec_groups))
        logger.debug(f'Instance security groups: {sec_groups}')

        ec2 = boto3.resource('ec2', region_name=self._region)
        # noinspection PyTypeChecker
        instances = ec2.create_instances(
            ImageId=ami_id,
            MinCount=num_instances,
            MaxCount=num_instances,
            InstanceType=instance_type,
            KeyName=self._key_name,
            SecurityGroupIds=sec_groups
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
                timeout = time.monotonic() + startup_timeout_s
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
            spawned_instances = {}

            try:
                for inst in tpool.map(_wait_for_instance, instances):
                    spawned_instances[inst.instance_id] = inst
            except TimeoutError as e:
                self._tear_down_instances(spawned_instances)
                raise CloudError() from e

        self._running_instances.update(spawned_instances)
        logger.info('EC2 instances are booted and ready.')
        return self

    def __enter__(self) -> CloudInstances:
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

    @staticmethod
    def _tear_down_instances(instances: Mapping[str, Instance]) -> None:
        with ThreadPoolExecutor() as tpool:
            def _shutdown_instance(instance: Instance):
                logger.debug(f'Terminating instance {instance.instance_id}...')
                instance.terminate()
                instance.wait_until_terminated()
                logger.warning(f'Instance {instance.instance_id} terminated.')

            # list() forces the .map() statement to be evaluated immediately
            list(tpool.map(_shutdown_instance, instances.values()))

    def tear_down_all_instances(self) -> None:
        # contextmanager shutting down, tear down and terminate all
        # the instances
        logger.warning(f'Shutting down all EC2 compute instances on region '
                       f'{self._region}...')
        self._tear_down_instances(self._running_instances)
        self._running_instances.clear()
        logger.warning(f'All EC2 instances on region {self._region} shut down.')

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
        self.tear_down_all_instances()
        self.clear_ephemeral_sec_groups()
