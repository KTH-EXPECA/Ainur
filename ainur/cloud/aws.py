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

from __future__ import annotations

import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass
from ipaddress import IPv4Address
from types import TracebackType
from typing import Any, Collection, Dict, Iterator, Mapping, \
    Set, \
    Type, overload

import boto3
from botocore.exceptions import ClientError
from loguru import logger
from mypy_boto3_ec2.service_resource import Instance, SecurityGroup
from mypy_boto3_ec2.type_defs import IpPermissionTypeDef, IpRangeTypeDef

from .errors import CloudError, RevokedKeyError
from .instances import spawn_instances, \
    tear_down_instances
from .keys import AWSKeyPair, AWSNullKeyPair
from .security_groups import create_security_group


@dataclass(frozen=True, eq=True)
class EC2Host:
    instance_id: str
    public_ip: IPv4Address
    vpc_ip: IPv4Address
    key_file: str  # TODO: might be redundant


class CloudInstances(AbstractContextManager, Mapping[str, EC2Host]):
    """
    Context manager for AWS EC2 instances.
    """

    # old default sec group: sg-0170fa039ff0a56c4

    def __init__(self,
                 region: str = 'eu-north-1',
                 default_sec_groups: Collection[str] = ()):
        """
        Parameters
        ----------
        region:
            AWS region on which to deploy instances.
        default_sec_groups
            Default, mandatory security groups to attach instances to.
        """

        self._running_instances: Dict[str, Instance] = {}
        self._region = region

        self._ssh_sec_groups: Set[str] = set()
        self._default_sec_groups: Set[str] = set(default_sec_groups)
        self._ephemeral_sec_groups: Set[SecurityGroup] = set()

        self._key = AWSNullKeyPair()

    @property
    def keyfile(self) -> str:
        return self._key.key_file_path

    def __str__(self):
        return f'CloudLayer(region: {self._region}, ' \
               f'running instances: {len(self._running_instances)})'

    def create_sec_group(self,
                         name: str,
                         desc: str,
                         ingress_rules: Collection[IpPermissionTypeDef] = (),
                         egress_rules: Collection[IpPermissionTypeDef] = (),
                         ephemeral: bool = True,
                         attach_to_instances: bool = True) -> str:

        sec_group = create_security_group(
            name=name,
            desc=desc,
            region=self._region,
            ingress_rules=ingress_rules,
            egress_rules=egress_rules
        )

        if ephemeral:
            self._ephemeral_sec_groups.add(sec_group)

        if attach_to_instances:
            try:
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

                    instance.modify_attribute(Groups=list(security_groups))

                    logger.debug(f'Updated security groups for instance {iid}: '
                                 f'{security_groups}')
            except Exception as e:
                logger.error(f'Could not attach security group {name} to '
                             f'running instances.')
                raise CloudError(
                    f'Failed to attach security group to instances '
                    f'{list(self._running_instances.keys())}.'
                ) from e

        return sec_group.group_id

    def clear_ephemeral_sec_groups(self) -> None:
        logger.warning('Deleting ephemeral security groups '
                       f'in region {self._region}...')
        for sec_group in self._ephemeral_sec_groups:
            logger.debug(f'Deleting security group {sec_group.group_name} '
                         f'({sec_group.description}, region {self._region})')

            try:
                self._ssh_sec_groups.remove(sec_group.group_id)
            except KeyError:
                pass

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

        if len(self._ssh_sec_groups) < 1:
            raise CloudError('No default SSH access security groups '
                             'available, aborting cloud instance spawning!')

        sec_groups = self._ssh_sec_groups \
            .union(self._default_sec_groups) \
            .union(additional_sec_groups)
        sec_groups = list(sec_groups)

        instances = spawn_instances(
            num_instances=num_instances,
            key_name=self._key.name,
            ami_id=ami_id,
            instance_type=instance_type,
            region=self._region,
            security_group_ids=sec_groups,
            startup_timeout_s=startup_timeout_s
        )
        self._running_instances.update({i.id: i for i in instances})
        return self

    def __enter__(self) -> CloudInstances:
        try:
            # verify that we have a key...
            ec2 = boto3.resource('ec2', region_name=self._region)
            key = ec2.KeyPair(self._key.name)
            key.load()
            logger.debug(f'Using key pair: {key.key_name}')
        except (RevokedKeyError, ClientError):
            # we don't have a key... create an ephemeral one
            self._key = AWSKeyPair(region=self._region)

        # verify that we have at least one ssh access security group
        # create one if we don't
        if len(self._ssh_sec_groups) == 0:
            logger.info('Creating ephemeral security group for SSH access to '
                        f'instances on region {self._region}.')
            ssh_sgid = self.create_sec_group(
                name=f'ainur-ssh-{uuid.uuid4().hex}',
                desc='SSH Access',
                ephemeral=True,
                attach_to_instances=False,
                ingress_rules=[
                    IpPermissionTypeDef(
                        FromPort=22,
                        ToPort=22,
                        IpProtocol='tcp',
                        IpRanges=[IpRangeTypeDef(CidrIp='0.0.0.0/0')]
                    )
                ]
            )
            self._ssh_sec_groups.add(ssh_sgid)

        return self

    def __iter__(self) -> Iterator[str]:
        return iter(self._running_instances)

    def __getitem__(self, item: str) -> EC2Host:
        inst = self._running_instances[item]
        return EC2Host(
            instance_id=inst.instance_id,
            public_ip=IPv4Address(inst.public_ip_address),
            vpc_ip=IPv4Address(inst.private_ip_address),
            key_file=self._key.key_file_path
        )

    def __len__(self) -> int:
        return len(self._running_instances)

    def __contains__(self, item: Any) -> bool:
        return item in self._running_instances

    def tear_down_all_instances(self) -> None:
        # contextmanager shutting down, tear down and terminate all
        # the instances
        logger.warning(f'Shutting down all EC2 compute instances on region '
                       f'{self._region}...')
        tear_down_instances(self._running_instances.values())
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
        self._key = self._key.revoke()
