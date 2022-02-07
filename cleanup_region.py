from typing import Collection

import boto3
import click
from botocore.exceptions import ClientError
from loguru import logger

from ainur.cloud import tear_down_instances


@click.command()
@click.argument('region', type=str)
@click.option('-i', '--skip-instance', 'skip_instances',
              type=str, multiple=True, default=(), show_default=True)
@click.option('-s', '--skip-security-group', 'skip_sec_groups',
              type=str, multiple=True, default=(), show_default=True)
@click.option('-k', '--skip-key', 'skip_keys',
              type=str, multiple=True,
              default=('ExPECA_AWS_Keys',), show_default=True)
@click.option('--enum', type=bool, default=False,
              show_default=True, is_flag=True)
def aws_cleanup(region: str,
                skip_instances: Collection[str],
                skip_sec_groups: Collection[str],
                skip_keys: Collection[str],
                enum: bool) -> None:
    """
    Deletes all (non-default) security groups, instances and keys in the given
    region, except those specified in the skip_ parameters.

    Parameters
    ----------

    region
        AWS region to operate on.

    skip_instances
        Instance IDs to skip deleting.

    skip_sec_groups
        Security group IDs/names to skip deleting.

    skip_keys
        Key pair IDs/names to skip deleting.

    enum
        Enumerate resources that would be deleted, but don't delete anything.

    """

    logger.info(f'Cleaning up region {region}.')

    ec2 = boto3.resource('ec2', region_name=region)
    instances = [inst for inst in ec2.instances.all()
                 if inst.instance_id not in skip_instances]
    if enum:
        for inst in instances:
            logger.info(f'Instance {inst.instance_id} would be deleted')
    else:
        tear_down_instances(instances)

    sec_groups = ec2.security_groups.all()
    for sec_group in sec_groups:
        if sec_group.id not in skip_sec_groups \
                and sec_group.group_name not in skip_sec_groups:
            if enum:
                logger.info(f'Group {sec_group.group_id}/'
                            f'{sec_group.group_name} would be deleted.')
            else:
                logger.warning(f'Deleting group {sec_group.group_id}.')
                try:
                    sec_group.delete()
                except ClientError as e:
                    logger.error(e)

    keys = ec2.key_pairs.all()
    for key in keys:
        if key.key_pair_id not in skip_keys \
                and key.key_name not in skip_keys:
            if enum:
                logger.info(f'Key {key.key_pair_id}/{key.key_name} would be '
                            f'deleted.')
            else:
                logger.warning(f'Deleting key {key.key_pair_id}.')
                try:
                    key.delete()
                except ClientError as e:
                    logger.error(e)


if __name__ == '__main__':
    aws_cleanup()
