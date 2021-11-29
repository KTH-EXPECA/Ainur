from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any

import ansible_runner
from dataclasses_json import dataclass_json
from frozendict import frozendict
from loguru import logger

from ..ansible import AnsibleContext
from ..hosts import DisconnectedWorkloadHost
from ..misc import docker_client_context


@dataclass_json
@dataclass(frozen=True, eq=True)
class DockerVolSpec:
    name: str
    driver: str
    driver_opts: frozendict[str, Any]


class ExperimentStorage(AbstractContextManager):
    """
    Brings up a Samba server for persistent Docker volumes for experiments.
    """

    def __init__(self,
                 workload_name: str,
                 storage_host: DisconnectedWorkloadHost,
                 ansible_ctx: AnsibleContext,
                 host_path: PathLike = '/opt/expeca/experiments',
                 daemon_port: int = 2375,
                 ansible_quiet: bool = True):
        # TODO: documentation
        # TODO: needs to be further parameterized so it can be configured
        #  from a file.

        logger.info(f'Initializing centralized storage for w'
                    f'workload {workload_name}.')

        # start by ensuring paths exists
        host_path = Path(host_path)
        exp_path = host_path / workload_name

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

        # save docker volume params

        self._docker_vol_params = DockerVolSpec(
            name=f'{workload_name}_smb_vol',
            driver='local',
            driver_opts=frozendict({
                'type'  : 'cifs',
                'device': f'//{storage_host.management_ip.ip}/expeca',
                'o'     : 'username=expeca,password=expeca'
            })
        )

    @property
    def docker_vol_name(self) -> str:
        return self.docker_vol_params['name']

    @property
    def docker_vol_params(self) -> DockerVolSpec:
        return self._docker_vol_params

    def __enter__(self) -> ExperimentStorage:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tear_down()

    def tear_down(self) -> None:
        logger.info('Tearing down centralized storage server.')
        self._container.stop()
