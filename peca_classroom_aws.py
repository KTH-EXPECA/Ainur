import uuid
from io import StringIO
from pathlib import Path
from typing import Collection

import ansible_runner
import boto3
import click
import yaml
from botocore.exceptions import ClientError
from loguru import logger

from ainur.ansible import AnsibleContext
from ainur.cloud import AWSKeyPair, create_security_group, spawn_instances, \
    ssh_ingress_rule, tear_down_instances


@click.group()
def cli():
    pass


@cli.command()
@click.argument('num_instances', type=int)
@click.argument('region', type=str)
@click.argument('config-file', type=click.File(mode='w'))
@click.option('-a', '--ami-id', type=str,
              default='ami-05411ec0f7e9b0109',
              show_default=True)
@click.option('-t', '--instance-type', type=str,
              default='t3.micro', show_default=True)
@click.option('--timeout', type=int,
              default=60 * 3, show_default=True)
def launch_instances(num_instances: int,
                     region: str,
                     config_file: StringIO,
                     ami_id: str,
                     instance_type: str,
                     timeout: int = 60 * 3) -> None:
    ansible_ctx = AnsibleContext(Path('./ansible_env'))
    with AWSKeyPair(region=region) as key:
        ssh_sg = create_security_group(
            name=f'peca-ssh-access-{uuid.uuid4().hex}',
            desc='Ephemeral SSH access for PECA classroom.',
            region=region,
            ingress_rules=[ssh_ingress_rule]
        )

        instances = spawn_instances(
            num_instances=num_instances,
            region=region,
            ami_id=ami_id,
            instance_type=instance_type,
            startup_timeout_s=timeout,
            key_name=key.name,
            security_group_ids=[ssh_sg.group_id]
        )

        inventory = {}
        logger.info('Spawned instances:')
        for inst in instances:
            logger.info(f'{inst.instance_id}: {inst.public_ip_address}')
            inventory[inst.instance_id] = {
                'ansible_user': 'ubuntu',
                'ansible_host': inst.public_ip_address,
            }

        # enable password auth
        inventory = {'all': {'hosts': inventory}}
        with ansible_ctx(inventory=inventory,
                         ssh_key=key.key_file_path) as tmp_dir:
            res = ansible_runner.run(
                playbook='peca_ssh_auth.yml',
                json_mode=False,
                private_data_dir=str(tmp_dir),
                quiet=False
            )

        if res.status == 'failed':
            logger.error(f'Failed to configure auth on instances.')
            tear_down_instances(instances)
            raise RuntimeError()

        record = {
            'region'        : region,
            'security-group': ssh_sg.group_id,
            'instances'     : [i.id for i in instances]
        }

        yaml_record = yaml.safe_dump(record)
        logger.info(f'Record:\n{yaml_record}')
        config_file.write(yaml_record)

    # input('Pause')
    # tear_down_instances(instances)
    # ssh_sg.delete()


@cli.command()
@click.argument('config-file',
                type=click.Path(file_okay=True, dir_okay=False, exists=True))
def tear_down_instances(config_file: str) -> None:
    with open(config_file, 'r') as fp:
        config = yaml.safe_load(fp)

    region = config['region']
    sg_id = config['security-group']
    instances = config['instances']
    assert isinstance(instances, Collection)

    ec2 = boto3.resource('ec2', region_name=region)

    # delete security group
    logger.info(f'Deleting security group {sg_id}.')
    try:
        sg = ec2.SecurityGroup(sg_id)
        sg.load()
        sg.delete()
    except ClientError:
        logger.error(f'Could not delete security group {sg_id}; does it exist?')

    # delete instances
    logger.info(f'Terminating instances: {list(instances)}')
    for iid in instances:
        logger.info(f'Terminating instance {iid}.')
        try:
            inst = ec2.Instance(iid)
            inst.load()
            inst.terminate()
            logger.debug(f'Terminated instance {iid}.')
        except ClientError:
            logger.error(f'Could not delete instance {iid}; does it exist?')

    # TODO: delete file?


if __name__ == '__main__':
    cli()
