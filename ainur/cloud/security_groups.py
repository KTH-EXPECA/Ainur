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
    ec2_client = boto3.client('ec2', region_name=region)
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

        # wait until exists
        waiter = ec2_client.get_waiter('security_group_exists')
        waiter.wait(GroupNames=[name], WaiterConfig={'Delay'      : 1,
                                                     'MaxAttempts': 30})

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
