from contextlib import contextmanager
from dataclasses import dataclass
from ipaddress import IPv4Interface, IPv4Network
from pathlib import Path
from typing import Generator, Mapping, Tuple

import ansible_runner

from .hosts import ConnectedWorkloadHost, DisconnectedWorkloadHost
from .util import ansible_temp_dir


# TODO: needs testing


@dataclass(frozen=True, eq=True)
class WorkloadNetwork:
    network_addr: IPv4Network
    hosts: Tuple[ConnectedWorkloadHost]


def bring_up_workload_network(
        ip_hosts: Mapping[IPv4Interface, DisconnectedWorkloadHost],
        playbook_dir: Path) -> WorkloadNetwork:
    """
    Bring up the workload network, assigning the desired IP addresses to the
    given hosts.

    Parameters
    ----------
    ip_hosts
        Mapping from desired IP addresses (given as IPv4 interfaces,
        i.e. addresses plus network masks) to hosts. Note that
        all given IP addresses must, be in the same network segment.
    playbook_dir
        TODO: remove

    Returns
    -------
    WorkloadNetwork
        A WorkloadNetwork object containing details of the created network.
    """

    # NOTE: mapping is ip -> host, and not host -> ip, since ip addresses are
    # unique in a network but a host may have more than one ip.

    # sanity check: all the addresses should be in the same subnet
    subnets = [k.network for k in ip_hosts]
    if not len(set(subnets)) == 1:
        raise RuntimeError('Provided IPv4 interfaces should all belong to the '
                           f'same network. Subnets: {subnets}')

    # build an Ansible inventory
    inventory = {
        'all': {
            'hosts': {
                host.name: {
                    'ansible_host': host.ansible_host,
                    'workload_nic': host.workload_nic,
                    'workload_ip' : str(interface)  # {ip}/{netmask}
                } for interface, host in ip_hosts.items()
            }
        }
    }

    # prepare a temp ansible environment and run the appropriate playbook
    with ansible_temp_dir(
            inventory=inventory,
            playbooks=['net_up.yml'],
            base_playbook_dir=playbook_dir
    ) as tmp_dir:
        res = ansible_runner.run(
            playbook='net_up.yml',
            json_mode=True,
            private_data_dir=str(tmp_dir),
            quiet=True,
        )

        # TODO: better error checking
        assert res.status != 'failed'

        # network is now up and running
        return WorkloadNetwork(
            network_addr=list(ip_hosts.keys())[0].network,
            hosts=tuple([
                ConnectedWorkloadHost(
                    name=h.name,
                    ansible_host=h.ansible_host,
                    workload_nic=h.workload_nic,
                    workload_ip=i
                )
                for i, h in ip_hosts.items()
            ])
        )


def tear_down_workload_network(network: WorkloadNetwork,
                               playbook_dir: Path) -> None:
    """
    Tears down a workload network.

    Parameters
    ----------
    network
        The WorkloadNetwork to tear down.
    playbook_dir
        TODO: remove
    """

    # build a temporary ansible inventory
    inventory = {
        'all': {
            'hosts': {
                host.name: {
                    'ansible_host': host.ansible_host,
                    'workload_nic': host.workload_nic,
                    'workload_ip' : str(host.workload_ip)  # {ip}/{netmask}
                } for host in network.hosts
            }
        }
    }

    # prepare a temp ansible environment and run the appropriate playbook
    with ansible_temp_dir(
            inventory=inventory,
            playbooks=['net_down.yml'],
            base_playbook_dir=playbook_dir
    ) as tmp_dir:
        res = ansible_runner.run(
            playbook='net_down.yml',
            json_mode=True,
            private_data_dir=str(tmp_dir),
            quiet=True,
        )

        # TODO: better error checking
        assert res.status != 'failed'
        # network is down


@contextmanager
def workload_network_ctx(
        ip_hosts: Mapping[IPv4Interface, DisconnectedWorkloadHost],
        playbook_dir: Path) -> Generator[WorkloadNetwork, None, None]:
    """
    Context manager for easy deployment and automatic teardown of workload
    networks.

    The created network instance is bound to the name given to the 'as' keyword.

    Parameters
    ----------
    ip_hosts
        Mapping from desired IP addresses (given as IPv4 interfaces,
        i.e. addresses plus network masks) to hosts. Note that
        all given IP addresses must, be in the same network segment.
    playbook_dir
        TODO: remove

    Yields
    ------
    WorkloadNetwork
        The created network instance.
    """
    # context manager for network, to simplify our lives a bit
    network = bring_up_workload_network(ip_hosts, playbook_dir)
    yield network
    tear_down_workload_network(network, playbook_dir)


# TODO: need a way to test this locally somehow?
if __name__ == '__main__':
    ip_hosts = {
        IPv4Interface('10.0.0.1/16') :
            DisconnectedWorkloadHost('elrond', 'elrond.expeca',
                                     workload_nic='enp4s0'),
        IPv4Interface('10.0.1.10/16'):
            DisconnectedWorkloadHost('client10', 'workload-client-10.expeca',
                                     workload_nic='eth0'),
        IPv4Interface('10.0.1.11/16'):
            DisconnectedWorkloadHost('client11', 'workload-client-11.expeca',
                                     workload_nic='eth0'),
        IPv4Interface('10.0.1.12/16'):
            DisconnectedWorkloadHost('client12', 'workload-client-12.expeca',
                                     workload_nic='eth0'),
    }

    pbook_dir = Path('./playbooks')

    with workload_network_ctx(ip_hosts, pbook_dir) as network:
        input(str(network))
