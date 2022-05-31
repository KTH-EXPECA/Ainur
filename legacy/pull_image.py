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

import itertools
from multiprocessing import Pool
from typing import Collection

import click
from docker import DockerClient
from loguru import logger

docker_port = 2375


def pull_image(url: str, image: str) -> None:
    client = DockerClient(base_url=f'{url}:{docker_port}')
    try:
        logger.info(f'Pulling image {image} on host {url}.')
        client.images.pull(image)
        logger.info(f'Pulled image {image} on host {url}.')
    except Exception as e:
        logger.exception(e)
    finally:
        client.close()


def parallel_pull_image(
        docker_host_addrs: Collection[str],
        image: str
) -> None:
    with Pool(processes=len(docker_host_addrs)) as pool:
        pool.starmap(
            pull_image,
            zip(docker_host_addrs, itertools.repeat(image))
        )


@click.command()
@click.argument('image', type=str)
def cli(image: str):
    hosts = [f'workload-client-{i:02d}.expeca' for i in range(13)] + \
            ['elrond.expeca']
    parallel_pull_image(hosts, image)


if __name__ == '__main__':
    cli()
