from __future__ import annotations

import warnings
from contextlib import AbstractContextManager, contextmanager
from typing import Collection, Generator

import docker.errors
from docker import DockerClient
from loguru import logger

from .hosts import ConnectedWorkloadHost
from .network import WorkloadNetwork


# TODO: check that added nodes belong to the original network?

@contextmanager
def docker_client_context(*args, **kwargs) \
        -> Generator[DockerClient, None, None]:
    """
    Utility context manager which simply creates a DockerClient with the
    provided arguments, binds it to the 'as' argument, and makes sure to
    close it on exiting the context.

    Parameters
    ----------
    args

    kwargs

    Yields
    ------
    DockerClient
        An initialized Docker client instance.
    """
    client = DockerClient(*args, **kwargs)
    yield client
    client.close()


class DockerSwarm(AbstractContextManager):
    """
    Implements an simple interface to a Docker swarm, built on top of a
    workload network. Can be used as a context manager, in which case the
    created instance is bound to the 'as' variable.

    Note that the Swarm is built up such that data traverses the workload
    network but management traffic stays on the management network.

    Example usage::

        with DockerSwarm(network, managers) as swarm:
            ...
            with swarm.manager_client_ctx() as client:
                client.services.ls()

            ...

    """

    _daemon_port = 2375

    class Warning(Warning):
        pass

    def __init__(self,
                 network: WorkloadNetwork,
                 managers: Collection[str]):
        """
        Parameters
        ----------
        network
            The WorkloadNetwork on top of which to build this swarm.

        managers
            The name identifiers of the manager nodes.
        """

        super(DockerSwarm, self).__init__()

        logger.info(f'Setting up a Docker Swarm on top of workload network '
                    f'{network.address}.')

        # filter out the managers
        mgr_hosts = set([h for h in network.hosts if h.name in managers])
        workers = network.hosts.difference(mgr_hosts)

        logger.info(f'Docker Swarm manager hosts: '
                    f'{[h.workload_ip for h in mgr_hosts]}')

        # initialize some containers to store nodes
        self._managers = set()
        self._workers = set()

        # initialize the swarm on a arbitrary first manager,
        # make the others join afterwards
        try:
            first_mgr = mgr_hosts.pop()
        except KeyError:
            # TODO: custom exception?
            raise RuntimeError('Need at least one manager node!')

        # connect to the docker daemon on the node
        # note that we connect from the management network, but the Swarm is
        # built on top of the workload network.
        with docker_client_context(
                base_url=f'{first_mgr.management_ip.ip}:{self._daemon_port}') \
                as client:
            logger.info(f'Initializing the Swarm on host {first_mgr}.')
            # initialize the swarm
            # listen and advertise Swarm management on the management
            # network, but send data through the workload network.
            client.swarm.init(
                listen_addr=str(first_mgr.management_ip.ip),
                advertise_addr=str(first_mgr.management_ip.ip),
                data_path_addr=str(first_mgr.workload_ip.ip)
            )

            # extract tokens
            tokens = client.swarm.attrs['JoinTokens']
            self._worker_token = tokens['Worker']
            self._manager_token = tokens['Manager']

            logger.info(f'Swarm worker token: {self._worker_token}')
            logger.info(f'Swarm manager token: {self._manager_token}')

            # save the first manager
            self._managers.add(first_mgr)

        # attach the rest of the nodes (if any)
        for manager in mgr_hosts:
            self.attach_manager(manager)

        for worker in workers:
            self.attach_worker(worker)

    def _attach_node(self,
                     node: ConnectedWorkloadHost,
                     join_token: str) -> None:
        # TODO: Add the host to the underlying network for consistency?

        # grab an arbitrary manager
        try:
            manager = self._managers.pop()
        except KeyError:
            # TODO: custom exception
            raise RuntimeError('Swarm has no managers!')

        logger.info(f'Attaching node {node} to the swarm.')
        try:
            with docker_client_context(
                    base_url=f'{node.management_ip.ip}:{self._daemon_port}'
            ) as client:
                if not client.swarm.join(
                        remote_addrs=[str(manager.management_ip.ip)],
                        join_token=join_token,
                        listen_addr=str(node.management_ip.ip),
                        advertise_addr=str(node.management_ip.ip),
                        data_path_addr=str(node.workload_ip.ip)
                ):
                    # TODO: custom exception here?
                    raise RuntimeError(f'{node} could not join swarm.')
        except docker.errors.APIError:
            # on error, we just tear down the whole thing
            self.tear_down()
            raise
        finally:
            # always return the manager to the pool
            self._managers.add(manager)

    def attach_worker(self, node: ConnectedWorkloadHost) -> None:
        """
        Attach a host in a worker capacity to this swarm.

        Parameters
        ----------
        node
        """
        self._attach_node(node, self._worker_token)
        self._workers.add(node)

    def attach_manager(self, node: ConnectedWorkloadHost) -> None:
        """
        Attach a host in a manager capacity to this swarm.

        Parameters
        ----------
        node
        """
        self._attach_node(node, self._manager_token)
        self._managers.add(node)

    def remove_node(self, node: ConnectedWorkloadHost) -> None:
        """
        Remove a node from this swarm.

        No-op if the node is not actually a part of the swarm.

        Parameters
        ----------
        node
        """

        # check that node is actually part of swarm
        # this of course only counts nodes added to the swarm through this
        # object
        if node in self._workers:
            logger.info(f'Removing worker {node} from the Swarm.')
            with docker_client_context(
                    base_url=f'{node.management_ip.ip}:{self._daemon_port}') \
                    as client:
                if not client.swarm.leave(force=True):
                    # TODO: custom exception here?
                    raise RuntimeError(f'{node} could not leave swarm.')
            self._workers.remove(node)

        elif node in self._managers:
            logger.info(f'Removing manager {node} from the Swarm.')
            with docker_client_context(
                    base_url=f'{node.management_ip.ip}:{self._daemon_port}') \
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

    def tear_down(self) -> None:
        """
        Convenience method to fully tear down this swarm.
        This object will be in an invalid state afterwards and should not be
        used any more.
        """

        logger.warning('Tearing down Swarm!')

        # need to copy, can't modify container during iteration
        workers = self._workers.copy()
        managers = self._managers.copy()

        for worker in workers:
            self.remove_node(worker)

        for manager in managers:
            self.remove_node(manager)

        logger.warning('Swarm has been torn down.')

    @contextmanager
    def manager_client_ctx(self) -> Generator[DockerClient, None, None]:
        """
        Returns a Docker client to a manager node wrapped in a context manager.

        Example usage::

            with swarm.manager_client_ctx() as client:
                client.services.ls()

        Yields
        ------
        DockerClient
            A Docker client attached to an arbitrary manager node.
        """
        mgr = self._managers.pop()
        self._managers.add(mgr)

        with docker_client_context(
                base_url=f'{mgr.management_ip.ip}:{self._daemon_port}'
        ) as client:
            yield client

    def __enter__(self) -> DockerSwarm:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # on exit, we tear down this swarm
        self.tear_down()
        return super(DockerSwarm, self).__exit__(exc_type, exc_val, exc_tb)
