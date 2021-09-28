import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Collection

import ansible_runner
import yaml


@dataclass
class Host:
    name: str
    ansible_host: str
    workload_ip: str


@dataclass
class DockerSwarm:
    manager: Host
    nodes: Collection[Host]
    join_token: str


def deploy_workload_swarm(manager: Host,
                          clients: Collection[Host],
                          playbook_dir: Path) -> DockerSwarm:
    # TODO: documentation
    # TODO: pretty logging

    # build a temporary Ansible inventory
    inventory = {
        'all': {
            'hosts'   : {
                'manager': asdict(manager),
            },
            'children': {
                'clients': {
                    'hosts': {
                        c.name: asdict(c) for c in clients
                    }
                }
            }
        },
    }

    # ansible-runner is stupid and expects everything to be an *actual* file
    # we will trick it by using temporary directories and files
    # on Linux this should all happen in a tmpfs, so no disk writes necessary
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)

        # set up the file structure ansible-runner expects, inside the tmpdir
        proj_dir = tmp_dir / 'project'
        proj_dir.mkdir(parents=True)

        inv_dir = tmp_dir / 'inventory'
        inv_dir.mkdir(parents=True)

        # link the playbook to the temp dir
        # shutil.copy(playbook_dir / 'swarm_up.yml', proj_dir)
        os.symlink(playbook_dir.resolve() / 'swarm_up.yml',
                   proj_dir / 'swarm_up.yml')

        # dump the inventory
        with (inv_dir / 'hosts').open('w') as fp:
            yaml.safe_dump(inventory, stream=fp)

        # now we can run shit
        # initialize the swarm
        init_res = ansible_runner.run(
            playbook='swarm_up.yml',
            json_mode=True,
            private_data_dir=str(tmp_dir),
            quiet=True,
        )

        try:
            assert init_res.status != 'failed'
        except AssertionError:
            input(tmp_dir)
            raise RuntimeError()

        # extract worker join token to store it
        events = list(init_res.host_events('manager'))
        join_token = events[-1]['event_data'] \
            ['res']['ansible_facts']['worker_join_token']

        return DockerSwarm(manager=manager,
                           nodes=clients,
                           join_token=join_token)


if __name__ == '__main__':
    host = Host(name='localhost',
                ansible_host='localhost',
                workload_ip='192.168.50.3')

    swarm = deploy_workload_swarm(manager=host, clients=[],
                                  playbook_dir=Path('../playbooks'))

    print(swarm)
