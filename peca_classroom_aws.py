import itertools
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass
from io import StringIO
from ipaddress import IPv4Interface, IPv4Network
from multiprocessing import Pool
from pathlib import Path
from typing import Collection, Deque, Dict, Tuple

import ansible_runner
import boto3
import click
import yaml
from botocore.exceptions import ClientError
from dataclasses_json import dataclass_json
from loguru import logger
from mypy_boto3_ec2 import ServiceResource
from mypy_boto3_ec2.service_resource import Instance, SecurityGroup
from mypy_boto3_ec2.type_defs import IpPermissionTypeDef, IpRangeTypeDef

from ainur.ansible import AnsibleContext
from ainur.cloud import AWSKeyPair, CloudError, create_security_group, \
    ssh_ingress_rule, \
    tear_down_instances
from ainur.cloud.instances import _wait_instances_up, spawn_instances

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


def make_ssh_secgroup(region: str):
    return create_security_group(
        name=f'peca-ssh-access-{uuid.uuid4().hex}',
        desc='Ephemeral SSH and VPN access for PECA classroom.',
        region=region,
        ingress_rules=[
            ssh_ingress_rule,
            IpPermissionTypeDef(
                FromPort=_vpn_port,
                ToPort=_vpn_port,
                IpRanges=[
                    IpRangeTypeDef(CidrIp='0.0.0.0/0')
                ],
                IpProtocol='tcp'
            ),
            IpPermissionTypeDef(
                FromPort=_vpn_port,
                ToPort=_vpn_port,
                IpRanges=[
                    IpRangeTypeDef(CidrIp='0.0.0.0/0')
                ],
                IpProtocol='udp'
            )
        ]
    )


def _configure_vpn_instance(
        instance: Instance,
        key: AWSKeyPair,
        vpn_ip: IPv4Interface,
        peer_ips: Collection[str]
) -> None:
    logger.info(f'Configuring VPN for instance {instance} '
                f'({instance.public_ip_address}.')
    logger.debug(f'VPN IP address: {vpn_ip}')

    inv_hosts = {
        instance.instance_id: {
            'ansible_user': 'ubuntu',
            'ansible_host': instance.public_ip_address,
            'vpn_port'    : _vpn_port,
            'vpn_ip'      : str(vpn_ip),
            'vpn_peers'   : list(peer_ips)
        }
    }

    inventory = {'all': {'hosts': inv_hosts}}

    with AnsibleContext(Path('./ansible_env'))(
            inventory=inventory,
            ssh_key=key.key_file_path
    ) as tmp_dir:
        for playbook in ('peca_ssh_auth.yml', 'peca_vpn.yml'):
            res = ansible_runner.run(
                playbook=playbook,
                json_mode=False,
                private_data_dir=str(tmp_dir),
                quiet=False
            )

        if res.status == 'failed':
            raise RuntimeError(f'Failed to configure instance.')


@dataclass_json
@dataclass(frozen=True, eq=True)
class MeshHost:
    region: str
    public_ip: str
    instance_id: str
    security_group: str


@dataclass_json
@dataclass(frozen=True, eq=True)
class Mesh:
    main_host: MeshHost
    offload_hosts: Tuple[MeshHost, ...]


def _spawn_mesh(
        main_region: str,
        offload_regions: Collection[str],
        instance_type: str = 't3.micro',
        timeout: int = 60 * 3,
        vpn_net: IPv4Network = IPv4Network('10.0.0.0/24')
) -> Mesh:
    logger.info('Spawning mesh.')
    logger.info(f'Main region: {main_region}')
    logger.info(f'Offload regions: {offload_regions}')

    ec2: Dict[str, ServiceResource] = {}
    keys: Dict[str, AWSKeyPair] = {}
    sec_groups: Dict[str, SecurityGroup] = {}
    instances: Deque[Instance] = deque()
    try:
        with ExitStack() as stack:
            # start offload instances
            offload_instances: Dict[str, Instance] = {}
            for region in set(offload_regions):
                ec2[region] = boto3.resource('ec2', region_name=region)
                keys[region] = stack.enter_context(AWSKeyPair(region=region))
                sec_groups[region] = make_ssh_secgroup(region)

                # spawn instances
                # noinspection PyTypeChecker
                offload_instances[region] = ec2[region].create_instances(
                    ImageId=_ami_ids[region],
                    MinCount=1,
                    MaxCount=1,
                    InstanceType=instance_type,
                    KeyName=keys[region].name,
                    SecurityGroupIds=[sec_groups[region].group_id]
                )[0]
                logger.debug(f'Spawned instance '
                             f'{offload_instances[region].instance_id} on '
                             f'region {region}.')
                instances.append(offload_instances[region])

            # start main instance
            if main_region not in ec2:
                ec2[main_region] = boto3.resource('ec2',
                                                  region_name=main_region)

            if main_region not in keys:
                keys[main_region] = stack.enter_context(
                    AWSKeyPair(region=main_region)
                )

            if main_region not in sec_groups:
                sec_groups[main_region] = make_ssh_secgroup(main_region)

            # noinspection PyTypeChecker
            main_instance = ec2[main_region].create_instances(
                ImageId=_ami_ids[main_region],
                MinCount=1,
                MaxCount=1,
                InstanceType=instance_type,
                KeyName=keys[main_region].name,
                SecurityGroupIds=[sec_groups[main_region].group_id]
            )[0]

            logger.debug(f'Spawned main instance {main_instance.instance_id} '
                         f'on region {main_region}.')

            instances.append(main_instance)

            # wait for instances to boot
            _wait_instances_up(instances,
                               startup_timeout_s=timeout,
                               poll_port=22)

            # instances are ready, now configure them
            with ThreadPoolExecutor(
                    max_workers=1 + len(offload_regions)
            ) as tpool:
                vpn_hosts = iter(vpn_net.hosts())

                main_future = tpool.submit(
                    _configure_vpn_instance,
                    instance=main_instance,
                    key=keys[main_region],
                    vpn_ip=next(vpn_hosts),
                    peer_ips=[
                        i.public_ip_address for i in offload_instances.values()
                    ]
                )

                vpn_ips = {
                    region: next(vpn_hosts)
                    for region in offload_regions
                }

                offload_futures = [
                    tpool.submit(
                        _configure_vpn_instance,
                        instance=offload_instances[region],
                        key=keys[region],
                        vpn_ip=vpn_ips[region],
                        peer_ips=[
                            i.public_ip_address for i in
                            offload_instances.values()
                            if i.id != offload_instances[region].id
                        ]
                    )
                    for region in offload_regions
                ]

                main_future.result()
                [f.result() for f in offload_futures]

            # configure main instance hosts file
            ansible_host = {
                main_region: {
                    'ansible_host' : main_instance.public_ip_address,
                    'ansible_user' : 'ubuntu',
                    'offload_hosts': {
                        str(vpn_ips[region]): region
                        for region in offload_regions
                    }
                }
            }

            with AnsibleContext(Path('./ansible_env'))(
                    inventory={'all': {'hosts': ansible_host}},
                    ssh_key=keys[main_region].key_file_path
            ) as tmp_dir:
                res = ansible_runner.run(
                    playbook='peca_hosts.yml',
                    json_mode=False,
                    private_data_dir=str(tmp_dir),
                    quiet=False
                )

                if res.status == 'failed':
                    raise RuntimeError('Failed to configure main instance.')

        # done, build result object
        return Mesh(
            main_host=MeshHost(
                region=main_region,
                instance_id=main_instance.instance_id,
                public_ip=main_instance.public_ip_address,
                security_group=sec_groups[main_region].group_id
            ),
            offload_hosts=tuple(
                [
                    MeshHost(
                        region=region,
                        instance_id=offload_instances[region].instance_id,
                        public_ip=offload_instances[region].public_ip_address,
                        security_group=sec_groups[region].group_id
                    )
                    for region in offload_regions
                ]
            )
        )

    except Exception as e:
        tear_down_instances(instances)
        for k in keys.values():
            k.revoke()
        for region, sg in sec_groups.items():
            delete_sg(sg.group_id, region=region)
        logger.error(e)
        raise e


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
@click.argument('num-meshes', type=int)
@click.argument('config-file', type=click.File(mode='w'))
@click.argument('main-region', type=str)
@click.argument('regions', type=str, nargs=-1)
@click.option('-t', '--instance-type', type=str,
              default='t3.micro', show_default=True)
@click.option('--timeout', type=int,
              default=60 * 3, show_default=True)
@click.option('--vpn-net', type=str, default='10.0.0.0/24', show_default=True)
def spawn_meshes(num_meshes: int,
                 main_region: str,
                 regions: Collection[str],
                 config_file: StringIO,
                 instance_type: str,
                 timeout: int = 60 * 3,
                 vpn_net: str = '10.0.0.0/24') -> None:
    vpn_net = IPv4Network(vpn_net)
    with Pool(processes=num_meshes) as pool:
        meshes = pool.starmap(
            _spawn_mesh,
            zip(
                itertools.repeat(main_region, num_meshes),
                itertools.repeat(regions, num_meshes),
                itertools.repeat(instance_type, num_meshes),
                itertools.repeat(timeout, num_meshes),
                itertools.repeat(vpn_net, num_meshes)
            )
        )

    yaml_record = yaml.safe_dump([mesh.to_dict() for mesh in meshes])
    logger.info(f'Record:\n{yaml_record}')
    config_file.write(yaml_record)


@cli.command()
@click.argument('region', type=str)
@click.option('-t', '--instance-type', type=str,
              default='t3.micro', show_default=True)
@click.option('--timeout', type=int,
              default=60 * 3, show_default=True)
@click.option('-u', '--tcp-port', 'tcp_ports', type=int, multiple=True,
              default=(), show_default=True)
@click.option('-u', '--udp-port', 'udp_ports', type=int, multiple=True,
              default=(), show_default=True)
def spawn_demo_instance(region: str,
                        instance_type: str,
                        timeout: int,
                        tcp_ports: Collection[int],
                        udp_ports: Collection[int]) -> None:

    docker_port = 2375
    tcp_ports = [docker_port] + list(tcp_ports)
    udp_ports = [docker_port] + list(udp_ports)

    ingress_rules = deque([ssh_ingress_rule])

    for port in tcp_ports:
        ingress_rules.append(
            IpPermissionTypeDef(
                FromPort=port, ToPort=port,
                IpRanges=[
                    IpRangeTypeDef(CidrIp='0.0.0.0/0')
                ],
                IpProtocol='tcp'
            )
        )

    for port in udp_ports:
        ingress_rules.append(
            IpPermissionTypeDef(
                FromPort=port, ToPort=port,
                IpRanges=[
                    IpRangeTypeDef(CidrIp='0.0.0.0/0')
                ],
                IpProtocol='udp'
            )
        )

    with AWSKeyPair(region=region) as key:
        # sec group first
        sec_group = create_security_group(
            name=f'peca-ssh-access-{uuid.uuid4().hex}',
            desc='Ingress for demo',
            region=region,
            ingress_rules=list(ingress_rules)
        )

        try:
            logger.info(f'Spawning instance in region {region}.')
            instance = spawn_instances(
                num_instances=1,
                key_name=key.name,
                ami_id=_ami_ids[region],
                instance_type=instance_type,
                region=region,
                security_group_ids=[sec_group.group_id],
                startup_timeout_s=timeout,
            )[0]
            logger.debug(f'Instance spawned: {instance.instance_id}')

            logger.info(f'Instance IP: {instance.public_ip_address}')
        except (CloudError, ClientError) as e:
            logger.warning(f'Deleting security group {sec_group.group_id}.')
            sec_group.delete()
            logger.error(e)
            return 1



# TODO: delete file?


if __name__ == '__main__':
    cli()
