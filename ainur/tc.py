from __future__ import annotations

from contextlib import AbstractContextManager

import ansible_runner
from loguru import logger

from .ansible import AnsibleContext
from .hosts import ConnectedWorkloadHost
from .tc_defs import *


class TrafficControl(AbstractContextManager):
    """
    Represents workload network traffic control
    Mainly used to manage traffic control of each host

    Can be used as a context manager
    """

    def __init__(self,
                 hosts: set[ConnectedWorkloadHost],
                 ansible_context: AnsibleContext,
                 quiet: bool = True):

        self._ansible_context = ansible_context
        self._traffic_info_samples = []
        self._hosts = hosts

        # take the first sample from the network
        self.sample(quiet=quiet)

    def sample(self, quiet: bool = True):

        inventory = {
            'all': {
                'hosts': {
                    host.ansible_host: {
                        'interface_name': host.workload_interface.name,
                    } for host in self._hosts
                }
            }
        }

        # prepare a temp ansible environment and run the appropriate playbook
        with self._ansible_context(inventory) as tmp_dir:

            res = ansible_runner.run(
                playbook='get_traffic_info.yml',
                json_mode=True,
                private_data_dir=str(tmp_dir),
                quiet=quiet,
            )

            # TODO: better error checking
            assert res.status != 'failed'

            for event in res.events:
                if "task" in event["event_data"]:
                    if (event["event_data"]["task"] == "report") and (
                            "res" in event["event_data"]):
                        # print(json.dumps(event["event_data"]["host"]))
                        # print(json.dumps(event["event_data"]["res"]["msg"]))
                        # print(event["event_data"]["res"]["msg"])
                        host_name = event["event_data"]["host"]

                        main_dict = event["event_data"]["res"]["msg"]
                        ip_conf = IpConf.from_dict(main_dict['ip'][0])
                        ip_rx_stats = IpRxStats.from_dict(
                            main_dict['ip'][0]['stats64']['rx'])
                        ip_tx_stats = IpTxStats.from_dict(
                            main_dict['ip'][0]['stats64']['tx'])

                        tc_q_list = []
                        for item in main_dict['tc']:
                            if ('root' in item):
                                if (item['root'] == True):
                                    item = {'parent': '0:', **item}

                            if (item['kind'] == "fq_codel"):
                                item = {**item['options'], **item}
                                item.pop('options', None)
                                tc_q_conf = CodelTxQueueConf.from_dict(item)
                                tc_q_stat = CodelTxQueueStats.from_dict(item)
                            else:
                                tc_q_conf = TcTxQueueConf.from_dict(item)
                                tc_q_stat = TcTxQueueStats.from_dict(item)

                            tc_q_list.append(
                                TcTxQueue(conf=tc_q_conf, stat=tc_q_stat))

                        net_ip = NetIpStats.from_dict(
                            main_dict['netstat']['Ip'])
                        net_udp = NetUdpStats.from_dict(
                            main_dict['netstat']['Udp'])
                        net_tcp = NetTcpStats.from_dict(main_dict['netstat'])
                        ns_stats = NetStats(ip=net_ip, udp=net_udp, tcp=net_tcp)

                        timestamp = int(main_dict['timestamp'])

                        sample = TrafficInfoSample(host=host_name,
                                                   timestamp=timestamp,
                                                   ip_conf=ip_conf,
                                                   ip_stats=(ip_rx_stats,
                                                             ip_tx_stats),
                                                   tc_queues=tc_q_list,
                                                   ns_stats=ns_stats)
                        self._traffic_info_samples.append(sample)

    def tear_down(self) -> None:
        """
        Removes all the added vlans.
        Note that after calling this method, this object will be left in an
        invalid state and should not be used any more.
        """
        logger.warning('Removing traffic control.')
        # TODO: Samie, this doesn't do anything?

    def __enter__(self) -> TrafficControl:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(TrafficControl, self).__exit__(exc_type, exc_val, exc_tb)
