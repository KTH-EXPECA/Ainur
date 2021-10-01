from contextlib import contextmanager
from dataclasses import dataclass
from ipaddress import IPv4Interface, IPv4Network
from typing import FrozenSet, Generator, Mapping

import ansible_runner

from ainur.ansible import AnsibleContext
from ainur.hosts import ConnectedWorkloadHost, DisconnectedWorkloadHost


# TODO: needs testing


@dataclass(frozen=True, eq=True)
class WorkloadNetwork:
    network_addr: IPv4Network
    hosts: FrozenSet[ConnectedWorkloadHost]


def bring_up_workload_network(
        ip_hosts: Mapping[IPv4Interface, DisconnectedWorkloadHost],
        ansible_context: AnsibleContext) -> WorkloadNetwork:
    """
    Bring up the workload network, assigning the desired IP addresses to the
    given hosts.

    Parameters
    ----------
    ip_hosts
        Mapping from desired IP addresses (given as IPv4 interfaces,
        i.e. addresses plus network masks) to hosts. Note that
        all given IP addresses must, be in the same network segment.
    ansible_context:
        Ansible context to use.

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
    with ansible_context(inventory) as tmp_dir:
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
            hosts=frozenset([
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
                               ansible_context: AnsibleContext) -> None:
    """
    Tears down a workload network.

    Parameters
    ----------
    network
        The WorkloadNetwork to tear down.
    ansible_context
        Ansible context to use.
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
    with ansible_context(inventory) as tmp_dir:
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
        ansible_context: AnsibleContext) \
        -> Generator[WorkloadNetwork, None, None]:
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
    ansible_context
        Ansible context to use.

    Yields
    ------
    WorkloadNetwork
        The created network instance.
    """
    # context manager for network, to simplify our lives a bit
    network = bring_up_workload_network(ip_hosts, ansible_context)
    yield network
    tear_down_workload_network(network, ansible_context)

# TODO: need a way to test network locally
