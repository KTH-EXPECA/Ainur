from __future__ import annotations

import abc
import os
import shutil
import socket
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Collection, List, Optional

import boto3
from botocore.exceptions import ClientError
from loguru import logger
from mypy_boto3_ec2.service_resource import Instance, SecurityGroup, Vpc
from mypy_boto3_ec2.type_defs import IpPermissionTypeDef

from ainur.cloud import CloudError


def spawn_instances(num_instances: int,
                    key_name: str,
                    ami_id: str,
                    instance_type: str,
                    region: str,
                    security_group_ids: Collection[str] = (),
                    startup_timeout_s: int = 60 * 3) -> List[Instance]:
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

    # wait until instances are running and are accessible on port 22
    with ThreadPoolExecutor() as tpool:
        def _wait_for_instance(inst: Instance):
            # first wait until instance is "running"
            # (does not mean the OS is fully initialized though)
            inst.wait_until_running()
            inst.reload()
            logger.debug(f'Instance {inst.instance_id} is running.')

            # now, attempt to open a socket connection to port 22 to verify
            # that the instance is ready
            timeout = time.monotonic() + startup_timeout_s
            while time.monotonic() <= timeout:
                with socket.socket(socket.AF_INET,
                                   socket.SOCK_STREAM) as sock:
                    try:
                        sock.connect((inst.public_ip_address, 22))
                        # connected, return
                        logger.info(f'Instance {inst.instance_id} is '
                                    f'ready.')
                        return inst
                    except (TimeoutError, ConnectionRefusedError):
                        continue

            # could not connect
            # force the instance to terminate and raise an exception
            logger.warning(f'Time-out for instance {inst.instance_id}.')
            logger.warning('Aborting.')
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

    logger.info('EC2 instances are booted and ready.')
    return spawned_instances


def tear_down_instances(instances: Collection[Instance]) -> List[str]:
    with ThreadPoolExecutor() as tpool:
        def _shutdown_instance(instance: Instance) -> str:
            iid = instance.instance_id
            logger.debug(f'Terminating instance {instance.instance_id}...')
            instance.terminate()
            instance.wait_until_terminated()
            logger.warning(f'Instance {instance.instance_id} terminated.')
            return iid

        # list() forces the .map() statement to be evaluated immediately
        return list(tpool.map(_shutdown_instance, instances))


def create_security_group(name: str,
                          desc: str,
                          region: str,
                          ingress_rules: Collection[IpPermissionTypeDef] = (),
                          egress_rules: Collection[IpPermissionTypeDef] = ()) \
        -> SecurityGroup:
    logger.info(f'Creating security group {name} ({desc}) in region {region}.')
    logger.debug(f'Ingress rules:\n{ingress_rules}')
    logger.debug(f'Egress rules:\n{egress_rules}')

    ec2 = boto3.resource('ec2', region_name=region)
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
            SourceSecurityGroupName=sec_group.group_name
        )

        # other ingress and egress rules
        if len(ingress_rules) > 0:
            sec_group.authorize_ingress(IpPermissions=ingress_rules)
        sec_group.authorize_egress(IpPermissions=egress_rules)

        logger.info(f'Created security group {name} with id '
                    f'{sec_group.group_id} in region {region}')
        return sec_group
    except Exception as e:
        logger.error(f'Could not create/configure security group {name}.')
        raise CloudError(
            f'Failed to create security group {name} ({desc}) in '
            f'region {region}.'
        ) from e


class RevokedKeyError(Exception):
    pass


class AWSKeyPairBase(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def private_key(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def key_file_path(self) -> str:
        pass

    @abc.abstractmethod
    def revoke(self) -> AWSKeyPairBase:
        pass


class AWSNullKeyPair(AWSKeyPairBase):
    @property
    def name(self) -> str:
        raise RevokedKeyError()

    @property
    def private_key(self) -> str:
        raise RevokedKeyError()

    @property
    def key_file_path(self) -> str:
        raise RevokedKeyError()

    def revoke(self) -> AWSKeyPairBase:
        return self


class AWSKeyPair(AWSKeyPairBase):
    def __init__(self, region: str, name: Optional[str] = None):
        # request new keypair from AWS
        ec2 = boto3.resource('ec2', region_name=region)
        key_name = name if name is not None else f'key-{uuid.uuid4().hex}'

        logger.info(f'Creating ephemeral key pair {key_name} for instance '
                    f'access on region {region}.')

        self._key = ec2.create_key_pair(KeyName=key_name)
        self._region = region

        self._key_dir = Path(tempfile.mkdtemp(prefix='ainur_')).resolve()
        self._key_file = (self._key_dir / f'{uuid.uuid4().hex}').resolve()

        # store key to file
        with self._key_file.open('w') as fp:
            fp.write(self._key.key_material)

        os.chmod(self._key_file, 0o600)

        logger.debug(f'Key {key_name} has been created and stored on-disk '
                     f'at {self._key_file}.')

        self._revoked = False

    def _check(self) -> None:
        if self._revoked:
            raise RevokedKeyError()

    @property
    def name(self) -> str:
        self._check()
        return self._key.key_name

    @property
    def private_key(self) -> str:
        self._check()
        return self._key.key_material

    @property
    def key_file_path(self) -> str:
        self._check()
        return str(self._key_file)

    def revoke(self) -> AWSKeyPairBase:
        if self._revoked:
            return AWSNullKeyPair()

        logger.warning(f'Revoking AWS key {self.name}...')
        shutil.rmtree(self._key_dir)

        # delete the key from ec2
        try:
            ec2 = boto3.resource('ec2', region_name=self._region)
            key = ec2.KeyPair(self._key.name)
            key.load()
            logger.debug(f'Deleting ephemeral key {key.key_name} on AWS...')
            key.delete()
        except ClientError:
            pass

        self._revoked = True
        logger.debug('Key revoked.')
        return AWSNullKeyPair()
