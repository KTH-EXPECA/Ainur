from __future__ import annotations

from typing import Collection

import boto3
from loguru import logger
from mypy_boto3_ec2.service_resource import SecurityGroup, Vpc
from mypy_boto3_ec2.type_defs import IpPermissionTypeDef, IpRangeTypeDef

from .errors import CloudError


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


ssh_ingress_rule = IpPermissionTypeDef(
    FromPort=22,
    ToPort=22,
    IpProtocol='tcp',
    IpRanges=[IpRangeTypeDef(CidrIp='0.0.0.0/0')]
)
