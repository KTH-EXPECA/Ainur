import uuid
from collections import defaultdict, deque
from contextlib import ExitStack
from dataclasses import dataclass
from io import StringIO
from ipaddress import IPv4Network
from pathlib import Path
from typing import Collection, Dict, Set, Tuple

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
class SpawnedInstance:
    id: str
    public_ip: str
    # vpn_ip: str


@dataclass_json
@dataclass(frozen=True, eq=True)
class SpawnRecord:
    region: str
    security_group: str
    vpn_ip: str
    instances: Tuple[SpawnedInstance, ...]


def delete_sg(sg_id: str, region: str) -> None:
    ec2 = boto3.resource('ec2', region_name=region)
    logger.info(f'Deleting security group {sg_id}.')
    try:
        sg = ec2.SecurityGroup(sg_id)
        sg.load()
        sg.delete()
    except ClientError as e:
        logger.error(e)


@click.group()
def cli():
    pass


@cli.command()
@click.argument('num_instances', type=int)
@click.argument('config-file', type=click.File(mode='w'))
@click.argument('regions', type=str, nargs=-1)
@click.option('-t', '--instance-type', type=str,
              default='t3.micro', show_default=True)
@click.option('--timeout', type=int,
              default=60 * 3, show_default=True)
def spawn_meshes(num_instances: int,
                 regions: Collection[str],
                 config_file: StringIO,
                 instance_type: str,
                 timeout: int = 60 * 3) -> None:
    keys_per_reg: Dict[str, AWSKeyPair] = {}
    instances_per_reg: Dict[str, Collection[Instance]] = {}
    sec_groups_per_reg: Dict[str, str] = {}
    peers: Dict[str, Set[str]] = defaultdict(set)

    try:
        with ExitStack() as stack:
            for region in regions:
                ami_id = _ami_ids[region]
                key = AWSKeyPair(region=region)
                keys_per_reg[region] = key
                stack.enter_context(key)

                ssh_sg = create_security_group(
                    name=f'peca-ssh-access-{uuid.uuid4().hex}',
                    desc='Ephemeral SSH access for PECA classroom.',
                    region=region,
                    ingress_rules=[ssh_ingress_rule]
                )
                sec_groups_per_reg[region] = ssh_sg.group_id

                instances = spawn_instances(
                    num_instances=num_instances,
                    region=region,
                    ami_id=ami_id,
                    instance_type=instance_type,
                    startup_timeout_s=timeout,
                    key_name=key.name,
                    security_group_ids=[ssh_sg.group_id]
                )
                logger.info('Spawned instances.')

                for other_r, other_insts in instances_per_reg.items():
                    for peer1, peer2 in zip(instances, other_insts):
                        logger.debug(f'{peer1.instance_id}: '
                                     f'{peer1.public_ip_address}')
                        peers[peer1.public_ip_address].add(
                            peer2.public_ip_address)
                        peers[peer2.public_ip_address].add(
                            peer1.public_ip_address)

                instances_per_reg[region] = instances

            # spawned all instances
            # configure ssh and vpn
            records = deque()
            vpn_net = IPv4Network('10.0.0.0/24')
            for region, vpn_ip in zip(regions, vpn_net.hosts()):
                logger.info(f'Configuring instances on region {region}.')
                logger.debug(f'Region {region} VPN IP address: {vpn_ip}')

                instances = instances_per_reg[region]
                inv_hosts = {
                    inst.instance_id: {
                        'ansible_user': 'ubuntu',
                        'ansible_host': inst.public_ip_address,
                        'vpn_port'    : _vpn_port,
                        'vpn_ip'      : str(vpn_ip),
                        'vpn_peers'   : list(peers[inst.public_ip_address])
                    } for inst in instances
                }

                # enable password auth
                inventory = {'all': {'hosts': inv_hosts}}
                ansible_ctx = AnsibleContext(Path('./ansible_env'))
                with ansible_ctx(
                        inventory=inventory,
                        ssh_key=keys_per_reg[region].key_file_path
                ) as tmp_dir:

                    for playbook in ('peca_ssh_auth.yml', 'peca_vpn.yml'):
                        res = ansible_runner.run(
                            playbook=playbook,
                            json_mode=False,
                            private_data_dir=str(tmp_dir),
                            quiet=False
                        )

                    if res.status == 'failed':
                        logger.error(f'Failed to configure instances.')
                        for region, reg_instances in instances_per_reg.items():
                            tear_down_instances(reg_instances)
                        raise RuntimeError()

                records.append(
                    SpawnRecord(
                        region=region,
                        vpn_ip=str(vpn_ip),
                        security_group=sec_groups_per_reg[region],
                        instances=tuple([SpawnedInstance(
                            id=i.id,
                            public_ip=i.public_ip_address,
                        )
                            for i in instances_per_reg[region]])
                    ).to_dict()
                )
    except Exception as e:
        logger.warning('Exception, cleaning up.')
        for region, instances in instances_per_reg:
            tear_down_instances(instances)
            delete_sg(sec_groups_per_reg[region], region)
            raise e

    yaml_record = yaml.safe_dump(list(records))
    logger.info(f'Record:\n{yaml_record}')
    config_file.write(yaml_record)


@cli.command()
@click.argument('config-file',
                type=click.File(mode='r'))
def clean_up(config_file: StringIO) -> None:
    config = yaml.safe_load(config_file)
    records: Collection[SpawnRecord] = \
        [SpawnRecord.from_dict(c) for c in config]

    for record in records:
        ec2 = boto3.resource('ec2', region_name=record.region)

        # delete instances first, then sg
        def _load_instance(i: SpawnedInstance) -> Instance:
            inst = ec2.Instance(i.id)
            inst.load()
            return inst

        tear_down_instances(map(_load_instance, record.instances))

        # delete security group
        delete_sg(record.security_group, record.region)

    # TODO: delete file?


if __name__ == '__main__':
    cli()
