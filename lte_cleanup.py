from ipaddress import IPv4Interface, IPv4Network, IPv4Address
from threading import Lock
import os
import docker
import time
from pathlib import Path
from autoran.oailte.epc import EvolvedPacketCore
from autoran.oailte.enodeb import ENodeB
from autoran.oailte.ue  import LTEUE
from autoran.utils import DockerNetwork
from loguru import logger

from autoran.utils.command_runner import RemoteRunner, terminate_container

class RouterCleaner():
    def __init__(self,
        client: docker.APIClient,
    ):
        self.client = client
        self.rr = RemoteRunner(
            client=self.client,
            name='prod-remoterunner',
        )
        # thread-safe
        self.mutex = Lock()

    def iptables_command(self,command_str):

        container = self.client.create_container(
            image='router_admin:latest',
            name='iptables_saver',
            hostname='ubuntu',
            volumes=['/tmp/'],
            host_config=self.client.create_host_config(
                network_mode='host',
                privileged=True,
                binds=[
                    '/tmp/:/tmp/',
                ],
            ),
            command="/bin/bash -c  \" " + command_str + " && echo 'OK' \" "
        )

        # start the container
        self.client.start(container)

        success = False
        for i in range(1,10):
            time.sleep(0.1)
            logs = self.client.logs(container,stdout=True, stderr=True, tail='all')
            logs = logs.decode().rstrip()
            #print(logs)
            if "OK" in logs:
                success = True
                break
        if not success:
            logger.error('Running the command: \" ' + command_str + " \" did not work on {0}".format(self.client.base_url))
            terminate_container(self.client,container)
            return False
            #raise Exception('Running the routing command: \" ' + command + " \" did not work on {0}".format(client.base_url))

        terminate_container(self.client,container)
        return True


    def restore_iptables(self):

        self.mutex.acquire()

        command_str = "iptables-restore < /tmp/dsl.fw"
        self.iptables_command(command_str)

        logger.warning('Router at {0} restored iptables.'.format(self.client.base_url))

        self.mutex.release()

    def remove_tunnel_route(self,
        target_net: str,
    ):
        self.mutex.acquire()

        self.rr.run_command("ip route del {0}".format(target_net))
        logger.warning('Router at {0} deleted route to network {1}'.format(self.client.base_url,target_net))

        self.mutex.release()


    def remove_tunnel(self,
        name: str,
    ):
        self.mutex.acquire()

        self.rr.run_command("ip tunnel del {0}".format(name))
        logger.warning('Router at {0} deleted tunnel {1}'.format(self.client.base_url,name))

        self.mutex.release()

    def start(self, route_target_nets, tunnel, docker_public_network):

        # clean the iptables
        self.restore_iptables()

        # clean the ext_routes
        for target_net in route_target_nets:
            self.remove_tunnel_route(target_net)

        # clean the tunnels
        self.remove_tunnel(tunnel)

        # clean first route command
        self.rr.run_command("ip route del {0} ".format(docker_public_network))
        logger.warning('Router at {0} deleted route to network {1}.'.format(self.client.base_url,docker_public_network))

        # stop all containers
        
def kill_container(name, client):

    containers = client.containers(all=True,filters={'name':name})
    logger.warning("Tearing down service {0} at {1}.".format(name,client.base_url))
    if len(containers) == 0:
        logger.error("Service {0} is not running at {1}.".format(name,client.base_url))
    else:
        try:
            client.kill(containers[0])
        except Exception as e:
            logger.error(str(e))

        try:
            client.remove_container(containers[0])
        except Exception as e:
            logger.error(str(e))

def kill_network(name, client):

    networks = client.networks(names=[name])
    logger.warning("Tearing down network {0} at {1}.".format(name,client.base_url))
    if len(networks) == 0:
        logger.error("Network {0} does not exist at {1}.".format(name,client.base_url))
    else:
        try:
            client.remove_network(networks[0]['Id'])
        except Exception as e:
            logger.error(str(e))


def main():

    # UE clean up
    host = "192.168.2.1"
    docker_port = '2375'
    logger.info('Starting LTE UE cleaner on {0}'.format(host))
    client = docker.APIClient(base_url=host+':'+docker_port)
    kill_container('iptables_saver', client)
    kill_container('prod-remoterunner', client)
    ue_cleaner = RouterCleaner(client)
    
    route_target_nets = ['10.4.0.0/24']
    tunnel = 'tun0'
    docker_public_network = '192.168.61.192/26'
    ue_cleaner.start(route_target_nets, tunnel, docker_public_network)
    
    kill_container('prod-oai-lte-ue',client)

    # EPC clean up
    host = "192.168.2.2"
    docker_port = '2375'
    logger.info('Starting LTE EPC cleaner on {0}'.format(host))
    client = docker.APIClient(base_url=host+':'+docker_port)
    kill_container('iptables_saver', client)
    kill_container('prod-remoterunner', client)
    epc_cleaner = RouterCleaner(client)

    route_target_nets = ['10.5.0.0/24']
    tunnel = 'tun0'
    ue_network = '12.1.1.0/24'
    epc_cleaner.start(route_target_nets, tunnel, ue_network)

    # docker rm -f prod-oai-spgwu-tiny prod-oai-spgwc prod-oai-legacy-mme prod-oai-hss prod-cassandra prod-oai-enb

    kill_container('prod-oai-spgwu-tiny',client)
    kill_container('prod-oai-spgwc',client)
    kill_container('prod-oai-legacy-mme',client)
    kill_container('prod-oai-hss',client)
    kill_container('prod-cassandra',client)
    kill_container('prod-oai-enb',client)

    # docker network rm prod-oai-private-net prod-oai-public-net
    kill_network('prod-oai-private-net', client)
    kill_network('prod-oai-public-net', client)
    

if __name__ == "__main__":
    main()
