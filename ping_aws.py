from __future__ import annotations

import itertools
import os
import subprocess
import uuid
from collections import deque
from dataclasses import dataclass
from multiprocessing import Pool
from typing import Collection, Deque

import click
import parse
import yaml
from botocore.exceptions import ClientError
from dataclasses_json import dataclass_json
from loguru import logger
from mypy_boto3_ec2.service_resource import Instance, SecurityGroup
from mypy_boto3_ec2.type_defs import IpPermissionTypeDef, IpRangeTypeDef

from ainur.cloud import AWSKeyPair, CloudError, create_security_group, \
    spawn_instances, \
    ssh_ingress_rule, tear_down_instances

_summary_line = \
    'round-trip min/avg/max/stddev = {min:f}/{avg:f}/{max:f}/{stddev:f} ms'


@dataclass_json
@dataclass(frozen=True, eq=True)
class PingResult:
    ip: str
    min: float
    avg: float
    max: float
    stddev: float


def spawn_and_ping(region: str,
                   ami_id: str,
                   ping_count: int) -> PingResult:
    security_groups: Deque[SecurityGroup] = deque()
    instances: Deque[Instance] = deque()

    try:
        # create appropriate sec group
        ssh_sg = create_security_group(
            name=f'peca-ssh-access-{uuid.uuid4().hex}',
            desc='Ephemeral SSH and ICMP access for ping test.',
            region=region,
            ingress_rules=[
                ssh_ingress_rule,
                IpPermissionTypeDef(
                    IpRanges=[
                        IpRangeTypeDef(CidrIp='0.0.0.0/0')
                    ],
                    IpProtocol='icmp',
                    FromPort=-1, ToPort=-1
                ),
            ]
        )
        security_groups.append(ssh_sg)

        with AWSKeyPair(region=region) as key:
            ping_insts = spawn_instances(
                num_instances=1,
                region=region,
                ami_id=ami_id,
                instance_type='t3.micro',
                startup_timeout_s=60 * 3,
                key_name=key.name,
                security_group_ids=[ssh_sg.group_id]
            )
            instances.extend(ping_insts)
            inst = ping_insts[0]
            logger.info(f'Spawned instance in region {region}.')
            logger.info('Pinging...')

            ping_res = subprocess.run(
                ['ping', f'-c{ping_count}', f'{inst.public_ip_address}'],
                capture_output=True,
            )
            # parse output line:
            results = parse.parse(
                _summary_line,
                ping_res.stdout.splitlines()[-1].decode('utf8'))

            logger.debug(f'{region}: {results}')
            return PingResult(
                ip=inst.public_ip_address,
                **results.named
            )

    except (ClientError, CloudError) as e:
        logger.exception(e)
        return PingResult('', -1, -1, -1, -1)
    finally:
        logger.debug('Cleaning up.')
        tear_down_instances(instances)
        for sg in security_groups:
            logger.warning(f'Deleting security group {sg.group_id}...')
            sg.delete()


@click.command()
@click.argument('regions', type=str, nargs=-1)
@click.option('-c', '--count', type=int, default=10, show_default=True)
def ping_aws(regions: Collection[str], count: int) -> None:
    try:
        _ = os.environ['AWS_ACCESS_KEY_ID']
        _ = os.environ['AWS_SECRET_ACCESS_KEY']
    except KeyError:
        raise RuntimeError('Cannot locate AWS credentials.')

    with open('offload-ami-ids.yaml', 'r') as fp:
        amis = yaml.safe_load(fp)

    with Pool(processes=len(regions)) as pool:
        ping_results = pool.starmap(
            func=spawn_and_ping,
            iterable=zip(
                regions,
                map(lambda r: amis[r], regions),
                itertools.repeat(count)
            )
        )

        print(
            yaml.safe_dump(
                {
                    region: result.to_dict()
                    for region, result in zip(regions, ping_results)
                }
            )
        )


if __name__ == '__main__':
    ping_aws()
