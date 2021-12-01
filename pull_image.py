import itertools
from multiprocessing import Pool

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


@click.command()
@click.argument('image', type=str)
def cli(image: str):
    hosts = [f'workload-client-{i:02d}.expeca' for i in range(13)] + \
            ['elrond.expeca']
    with Pool(processes=len(hosts)) as pool:
        pool.starmap(
            pull_image,
            zip(hosts, itertools.repeat(image))
        )


if __name__ == '__main__':
    cli()
