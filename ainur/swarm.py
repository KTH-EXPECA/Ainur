from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import asdict
from pathlib import Path
from typing import Collection, Optional, Set

import ansible_runner

from .hosts import WorkloadHost
from .util import ansible_temp_dir


# TODO: rework. Use functions, skip Swarm object. Pass Workload Network
#  object. Don't use Ansible --- python-on-whales or docker-py should do the
#  trick; maybe need to set up docker daemons to listen on TCP though.


def _make_inventory(manager: WorkloadHost,
                    clients: Collection[WorkloadHost]) -> dict:
    """
    Creates a valid Ansible inventory for swarm deployment.

    Parameters
    ----------
    manager
        Manager host
    clients
        Collection of client hosts

    Returns
    -------
    dict
        A valid Ansible inventory.
    """
    return {
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


class DockerSwarm(AbstractContextManager):
    def __init__(self,
                 manager: WorkloadHost,
                 clients: Collection[WorkloadHost],
                 playbook_dir: Path):
        # TODO: documentation
        # TODO: pretty logging

        # build a temporary Ansible inventory
        self._inventory = _make_inventory(manager, clients)

        # ansible-runner is stupid and expects everything to be an *actual* file
        # we will trick it by using temporary directories and files
        # on Linux this should all happen in a tmpfs, so no disk writes
        # necessary
        with ansible_temp_dir(inventory=self._inventory,
                              playbooks=['swarm_up.yml'],
                              base_playbook_dir=playbook_dir) as tmp_dir:
            # now we can run shit
            # initialize the swarm
            init_res = ansible_runner.run(
                playbook='swarm_up.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=True,
            )

            # TODO: better error checking
            assert init_res.status != 'failed'

            # extract worker join token to store it
            events = list(init_res.host_events('manager'))
            join_token = events[-1]['event_data'] \
                ['res']['ansible_facts']['worker_join_token']

        self._manager = manager
        self._nodes = set(clients)
        self._token = join_token
        self._playbook_dir = playbook_dir
        self._torn_down = False

    def __str__(self) -> str:
        return str({
            'manager'   : self._manager,
            'nodes'     : [n for n in self._nodes],
            'join_token': self._token
        })

    @property
    def manager(self) -> WorkloadHost:
        return self.manager

    @property
    def nodes(self) -> Set[WorkloadHost]:
        return self._nodes

    @property
    def join_token(self) -> str:
        return self._token

    def tear_down(self) -> bool:
        if self._torn_down:
            return False

        with ansible_temp_dir(inventory=self._inventory,
                              playbooks=['swarm_down.yml'],
                              base_playbook_dir=self._playbook_dir) as tmp_dir:
            # tear it all down!
            res = ansible_runner.run(
                playbook='swarm_down.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=True,
            )
            assert res.status != 'failed'
            return True

    def __enter__(self) -> DockerSwarm:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> Optional[bool]:
        super(DockerSwarm, self).__exit__(exc_type, exc_value, traceback)
        self.tear_down()
        return False


if __name__ == '__main__':
    host = WorkloadHost(name='localhost',
                        ansible_host='localhost',
                        workload_ip='192.168.50.3')

    with DockerSwarm(manager=host, clients=[],
                     playbook_dir=Path('../playbooks')) as swarm:
        print(swarm)
