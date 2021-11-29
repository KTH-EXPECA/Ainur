from __future__ import annotations

from contextlib import AbstractContextManager
from os import PathLike
from pathlib import Path
from typing import Any

import ansible_runner
from frozendict import frozendict

from ainur import AnsibleContext, DisconnectedWorkloadHost
from ainur.misc import docker_client_context


class ExperimentStorage(AbstractContextManager):
    """
    Brings up a Samba server for persistent Docker volumes for experiments.
    """

    # TODO: logging

    def __init__(self,
                 experiment_name: str,
                 storage_host: DisconnectedWorkloadHost,
                 ansible_ctx: AnsibleContext,
                 host_path: PathLike = '/opt/expeca/experiments',
                 daemon_port: int = 2375,
                 ansible_quiet: bool = True):
        # start by ensuring paths exists
        host_path = Path(host_path)
        exp_path = host_path / experiment_name

        inventory = {
            'all': {
                'hosts': {
                    storage_host.ansible_host: {
                        'ansible_host': storage_host.ansible_host
                    }
                }
            }
        }

        with ansible_ctx(inventory) as ansible_path:
            res = ansible_runner.run(
                host_pattern='all',
                module='ansible.builtin.file',
                module_args=f'path={exp_path} state=directory',
                json_mode=True,
                private_data_dir=str(ansible_path),
                quiet=ansible_quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'

        # path exists, now set up smb server
        with docker_client_context(
                base_url=f'{storage_host.management_ip.ip}:{daemon_port}'
        ) as client:
            self._container = client.run(
                image='dperson/samba',
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

        self._docker_vol_params = frozendict({
            'name'       : f'{experiment_name}_smb_vol',
            'driver'     : 'local',
            'driver_opts': {
                'type'  : 'cifs',
                'device': f'//{storage_host.management_ip.ip}/expeca',
                'o'     : 'username=expeca,password=expeca'
            }
        })

    @property
    def docker_vol_name(self) -> str:
        return self.docker_vol_params['name']

    @property
    def docker_vol_params(self) -> frozendict[str, Any]:
        return self._docker_vol_params

    def __enter__(self) -> ExperimentStorage:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tear_down()

    def tear_down(self) -> None:
        self._container.stop()
