from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from typing import Dict

import boto3
import click
import yaml


def copy_ami_to_all_regions(
        source_ami_id: str,
        source_ami_region: str,
) -> Dict[str, str]:
    ec2 = boto3.resource('ec2', region_name=source_ami_region)
    ami = ec2.Image(id=source_ami_id)
    ami.load()

    ec2client = boto3.client('ec2', region_name=source_ami_region)
    response = ec2client.describe_regions()
    other_regions = {
        r['RegionName'] for r in response['Regions']
    }
    other_regions.remove(source_ami_region)
    other_regions = list(other_regions)

    with ThreadPoolExecutor() as tpool:
        def _copy_ami(region: str) -> str:
            _client = boto3.client('ec2', region_name=region)
            resp = _client.copy_image(
                Name=ami.name,
                Description=f'{ami.description} '
                            f'(copied from {source_ami_region})',
                SourceImageId=source_ami_id,
                SourceRegion=source_ami_region
            )

            return resp['ImageId']

        return {
            region: ami_id
            for region, ami_id in zip(other_regions,
                                      tpool.map(_copy_ami, other_regions))
        }


@click.command()
@click.argument('ami_id', type=str)
@click.argument('region', type=str)
@click.argument('output_file', type=click.File(mode='w'))
def copy_ami(
        ami_id: str,
        region: str,
        output_file: StringIO) -> None:
    results = copy_ami_to_all_regions(ami_id, region)
    results_yaml = yaml.safe_dump(results)

    print(results_yaml)
    output_file.write(results_yaml)


if __name__ == '__main__':
    copy_ami()
