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
