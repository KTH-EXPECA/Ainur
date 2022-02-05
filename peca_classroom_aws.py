import uuid
from dataclasses import dataclass
from io import StringIO
from ipaddress import IPv4Network
from pathlib import Path
from typing import Tuple

import ansible_runner
import boto3
import click
import yaml
from botocore.exceptions import ClientError
from dataclasses_json import dataclass_json
from loguru import logger
from mypy_boto3_ec2.service_resource import Instance

from ainur.ansible import AnsibleContext
from ainur.cloud import AWSKeyPair, create_security_group, spawn_instances, \
    ssh_ingress_rule, tear_down_instances

_vpn_port = 3210

_ami_ids = {
    'ap-northeast-1': 'ami-00cb30ece35fa32da',
    'ap-northeast-2': 'ami-06bcbb0bfac260e0f',
    'ap-northeast-3': 'ami-0156cb220cb61b994',
    'ap-south-1'    : 'ami-0e8aacf20c4873838',
    'ap-southeast-1': 'ami-0bca4e52cd5292955',
    'ap-southeast-2': 'ami-0ae94e16b21ed06e1',
    'ca-central-1'  : 'ami-05798e7dc60907f1e',
    'eu-central-1'  : 'ami-0ecbbe9977c983cad',
    'eu-north-1'    : 'ami-05411ec0f7e9b0109',
    'eu-west-1'     : 'ami-06e5540a6c79d4044',
    'eu-west-2'     : 'ami-0a7a5d414f92f1dee',
    'eu-west-3'     : 'ami-04c9a64d19e052209',
    'sa-east-1'     : 'ami-0b8a85a1e0732e19b',
    'us-east-1'     : 'ami-03d730b46047af1f8',
    'us-east-2'     : 'ami-0e7ac7e0827845241',
    'us-west-1'     : 'ami-048b95e56deba1a79',
    'us-west-2'     : 'ami-0d5dd0aeed486a031'
}


@dataclass_json
@dataclass(frozen=True, eq=True)
class SpawnRecord:
    region: str
    security_group: str
    instances: Tuple[str, ...]


@click.group()
def cli():
    pass


@cli.command()
@click.argument('num_instances', type=int)
@click.argument('region', type=str)
@click.argument('config-file', type=click.File(mode='w'))
@click.option('-t', '--instance-type', type=str,
              default='t3.micro', show_default=True)
@click.option('--timeout', type=int,
              default=60 * 3, show_default=True)
def launch_instances(num_instances: int,
                     region: str,
                     config_file: StringIO,
                     instance_type: str,
                     timeout: int = 60 * 3) -> None:
    ansible_ctx = AnsibleContext(Path('./ansible_env'))

    vpn_net = IPv4Network('10.0.0.0/24')
    vpn_hosts = iter(vpn_net.hosts())

    ami_id = _ami_ids[region]

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

        vpn_ip = next(vpn_hosts)
        for inst in instances:
            logger.info(f'{inst.instance_id}: {inst.public_ip_address}')
            inventory[inst.instance_id] = {
                'ansible_user': 'ubuntu',
                'ansible_host': inst.public_ip_address,
                'vpn_port'    : _vpn_port,
                'vpn_ip'      : str(vpn_ip),
                'vpn_peers'   : []
            }

        # enable password auth
        inventory = {'all': {'hosts': inventory}}
        with ansible_ctx(inventory=inventory,
                         ssh_key=key.key_file_path) as tmp_dir:

            for playbook in ('peca_ssh_auth.yml', 'peca_vpn.yml'):
                res = ansible_runner.run(
                    playbook=playbook,
                    json_mode=False,
                    private_data_dir=str(tmp_dir),
                    quiet=False
                )

            if res.status == 'failed':
                logger.error(f'Failed to configure instances.')
                tear_down_instances(instances)
                raise RuntimeError()

        record = SpawnRecord(
            region=region,
            security_group=ssh_sg.group_id,
            instances=tuple([i.id for i in instances])
        )

        yaml_record = yaml.safe_dump(record.to_dict())
        logger.info(f'Record:\n{yaml_record}')
        config_file.write(yaml_record)

    # input('Pause')
    # tear_down_instances(instances)
    # ssh_sg.delete()


@cli.command()
@click.argument('config-file',
                type=click.Path(file_okay=True, dir_okay=False, exists=True))
def clean_up(config_file: str) -> None:
    with open(config_file, 'r') as fp:
        config = yaml.safe_load(fp)

    record: SpawnRecord = SpawnRecord.from_dict(config)

    ec2 = boto3.resource('ec2', region_name=record.region)

    # delete instances first, then sg
    def _load_instance(iid: str) -> Instance:
        inst = ec2.Instance(iid)
        inst.load()
        return inst

    tear_down_instances(map(_load_instance, record.instances))

    # delete security group
    logger.info(f'Deleting security group {record.security_group}.')
    try:
        sg = ec2.SecurityGroup(record.security_group)
        sg.load()
        sg.delete()
    except ClientError as e:
        logger.exception(e)
        logger.error(e)

    # TODO: delete file?


if __name__ == '__main__':
    cli()
