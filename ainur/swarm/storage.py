from __future__ import annotations

import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from os import PathLike
from pathlib import Path
from typing import List, Tuple

import ansible_runner
from docker.errors import APIError
from docker.models.volumes import Volume
from loguru import logger

from .. import NetworkLayer
from ..ansible import AnsibleContext
from ..hosts import ConnectedWorkloadHost, WorkloadHost
from ..misc import docker_client_context


class ExperimentStorage(AbstractContextManager):
    """
    Brings up a Samba server for persistent Docker volumes for experiments.
    """

    def __init__(self,
                 storage_name: str,
                 storage_host: WorkloadHost,
                 network: NetworkLayer,
                 ansible_ctx: AnsibleContext,
                 host_path: PathLike = '/opt/expeca/experiments',
                 daemon_port: int = 2375,
                 ansible_quiet: bool = True):
        # TODO: documentation
        # TODO: needs to be further parameterized so it can be configured
        #  from a file.

        logger.info(f'Initializing centralized storage {storage_name}.')
        self._storage_name = storage_name
        self._vols: List[Tuple[ConnectedWorkloadHost, Volume]] = list()

        # start by ensuring paths exists
        host_path = Path(host_path)
        exp_path = host_path / storage_name

        inventory = {
            'all': {
                'hosts': {
                    storage_host.ansible_host: {
                        'ansible_host': storage_host.ansible_host
                    }
                }
            }
        }

        logger.info(f'Creating paths on storage host {storage_host}.')
        with ansible_ctx(inventory) as ansible_path:
            res = ansible_runner.run(
                host_pattern='all',
                module='ansible.builtin.file',
                module_args=f'path={exp_path} state=directory',
                json_mode=True,
                private_data_dir=str(ansible_path),
                quiet=ansible_quiet,
                cmdline='--become'
            )

            # TODO: better error checking
            assert res.status != 'failed'

        # path exists, now set up smb server
        logger.info(f'Deploying SMB/CIFS server on {storage_host}.')
        with docker_client_context(
                base_url=f'{storage_host.management_ip.ip}:{daemon_port}'
        ) as client:
            self._container = client.containers.run(
                image='dperson/samba',  # FIXME: hardcoded things!
                remove=True,
                name='smb-server',
                command='-p -u "expeca;expeca" '
                        '-s "expeca;/opt/expeca;no;no;no;expeca"',
                detach=True,
                ports={
                    '139': '139',
                    '445': '445'
                },
                volumes={
                    f'{exp_path}': {
                        'bind': '/opt/expeca',
                        'mode': 'rw'
                    }
                }
            )
            # storage server is now running

        try:
            # iterate over hosts, create docker volumes pointing to SMB server
            with ThreadPoolExecutor() as tpool:
                exceptions = deque()
                ex_cond = threading.Condition()

                def _add_storage(host: ConnectedWorkloadHost) \
                        -> Tuple[ConnectedWorkloadHost, Volume]:
                    logger.info(
                        f'Creating Docker volume for centralized storage '
                        f'{storage_name} on host {host}.')
                    try:
                        with docker_client_context(
                                base_url=f'{host.management_ip.ip}:'
                                         f'{daemon_port}'
                        ) as client:
                            host_ip = storage_host.management_ip.ip
                            return host, client.volumes.create(
                                name=f'{storage_name}',
                                driver='local',
                                driver_opts=
                                {
                                    'type'  : 'cifs',
                                    'device': f'//{host_ip}/expeca',
                                    'o'     : f'addr={host_ip},'
                                              f'username=expeca,password=expeca'
                                }
                            )
                    except Exception as e:
                        logger.critical(
                            'Exception when adding Docker volume on '
                            f'host {host}.'
                        )
                        logger.exception(e)
                        with ex_cond:
                            exceptions.append(e)
                            ex_cond.notify_all()
                        raise e

                self._vols.extend(tpool.map(_add_storage, network.values()))
                # error handling
                with ex_cond:
                    if len(exceptions) > 0:
                        raise exceptions.pop()
        except Exception as e:
            # in case of any exception, we need to bring down everything
            self.tear_down()
            raise e

    @property
    def docker_vol_name(self) -> str:
        return self._storage_name

    def __enter__(self) -> ExperimentStorage:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tear_down()

    def tear_down(self) -> None:
        logger.info('Tearing down centralized storage server.')

        with ThreadPoolExecutor() as tpool:
            exceptions = deque()
            exc_cond = threading.Condition()

            def _remove_vol(host_vol: Tuple[ConnectedWorkloadHost, Volume]):
                host, vol = host_vol
                wait = 0.01
                while True:
                    try:
                        vol.remove()
                        logger.info(f'Successfully removed Docker volume '
                                    f'{vol.name} from host {host}.')
                        return
                    except APIError as e:
                        if e.status_code == 409:
                            logger.warning(f'Volume {vol.name} on host {host} '
                                           f'is busy, waiting to remove.')
                            # duplicate waiting time on each try
                            time.sleep(wait)
                            wait *= 2
                        else:
                            logger.exception(e)
                            with exc_cond:
                                exceptions.append(e)
                                exc_cond.notify_all()
                            raise e

            tpool.map(_remove_vol, self._vols)

        self._container.stop()
        with exc_cond:
            if len(exceptions) > 0:
                raise exceptions.pop()
