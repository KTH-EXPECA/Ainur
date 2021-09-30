from __future__ import annotations

# TODO: rework. Use functions, skip Swarm object. Pass Workload Network
#  object. Don't use Ansible --- python-on-whales or docker-py should do the
#  trick; maybe need to set up docker daemons to listen on TCP though.
import warnings
from contextlib import AbstractContextManager
from typing import Collection

from ainur.hosts import ConnectedWorkloadHost
from ainur.network import WorkloadNetwork
from ainur.util import docker_client_context


class DockerSwarm(AbstractContextManager):
    _docker_port = 2375

    class Warning(Warning):
        pass

    def __init__(self,
                 network: WorkloadNetwork,
                 managers: Collection[str]):
        super(DockerSwarm, self).__init__()

        # filter out the managers
        mgr_hosts = set([h for h in network.hosts if h.name in managers])
        workers = network.hosts.difference(mgr_hosts)

        # initialize some containers to store nodes
        self._managers = set()
        self._workers = set()

        # initialize the swarm on a arbitrary first manager,
        # make the others join afterwards
        first_mgr = mgr_hosts.pop()

        # connect to the docker daemon on the node
        # note that we connect from the management network, but the Swarm is
        # built on top of the workload network.
        with docker_client_context(
                base_url=f'{first_mgr.ansible_host}:{self._docker_port}') \
                as client:
            # initialize the swarm
            client.swarm.init(
                advertise_addr=str(first_mgr.workload_ip),
                listen_addr=str(first_mgr.workload_ip)
            )

            # extract tokens
            tokens = client.swarm.attrs['JoinTokens']
            self._worker_token = tokens['Worker']
            self._manager_token = tokens['Manager']

            # save the first manager
            self._managers.add(first_mgr)

        # attach the rest of the nodes (if any)
        for manager in mgr_hosts:
            self.add_manager(manager)

        for worker in workers:
            self.add_worker(worker)

    def _add_node(self, node: ConnectedWorkloadHost, join_token: str) -> None:
        # grab an arbitrary manager
        manager = self._managers.pop()

        with docker_client_context(
                base_url=f'{node.ansible_host}:{self._docker_port}') as client:
            if not client.swarm.join(
                    remote_addrs=[str(manager.workload_ip)],
                    join_token=join_token,
                    listen_addr=str(node.workload_ip),
                    advertise_addr=str(node.workload_ip)
            ):
                # TODO: custom exception here?
                raise RuntimeError(f'{node} could not join swarm.')

        # return the manager to the pool
        self._managers.add(manager)

    def add_worker(self, node: ConnectedWorkloadHost) -> None:
        self._add_node(node, self._worker_token)

    def add_manager(self, node: ConnectedWorkloadHost) -> None:
        self._add_node(node, self._manager_token)

    def remove_node(self, node: ConnectedWorkloadHost) -> None:
        # check that node is actually part of swarm
        # this of course only counts nodes added to the swarm through this
        # object
        if node in self._workers:
            with docker_client_context(
                    base_url=f'{node.ansible_host}:{self._docker_port}') \
                    as client:
                if not client.swarm.leave():
                    # TODO: custom exception here?
                    raise RuntimeError(f'{node} could not leave swarm.')
            self._workers.remove(node)

        elif node in self._managers:
            with docker_client_context(
                    base_url=f'{node.ansible_host}:{self._docker_port}') \
                    as client:
                if not client.swarm.leave(force=True):
                    # TODO: custom exception here?
                    raise RuntimeError(f'{node} could not leave swarm.')

            self._managers.remove(node)

            if len(self._managers) == 0:
                # if last manager, raise a warning
                # also remove all the workers
                warnings.warn(
                    'Last remaining manager has been removed; '
                    'swarm is now invalid.', self.Warning
                )
                self._workers.clear()
        else:
            # no-op if the node isn't part of the Swarm
            return

    def __enter__(self) -> DockerSwarm:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # on exit, we delete this swarm
        for manager in self._managers:
            self.remove_node(manager)

        return False
