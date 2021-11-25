from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from dataclasses import asdict
from dataclasses_json import dataclass_json
from dataclasses_json import Undefined
from dacite import from_dict
from prettyprinter import pprint
import prettyprinter
prettyprinter.install_extras(exclude=['ipython','ipython_repr_pretty','django'])

import json

@dataclass(frozen=True, eq=True)
class Stats():
    def __sub__(self, other):
        dict_self = asdict(self)
        dict_other = asdict(other)
        for t in dict_other.items():
            dict_self[t[0]] = dict_self[t[0]]-t[1]
        new_obj = from_dict(data_class=type(other), data=dict_self)
        return new_obj

############################

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True, eq=True)
class IpConf():
    operstate: str
    txqlen: int
    mtu: int
    qdisc: str
    link_type: str

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True, eq=True)
class IpStats(Stats):
    bytes: int
    packets: int
    errors: int
    dropped: int
    fifo_errors: int

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True, eq=True)
class IpRxStats(IpStats):
    over_errors: int
    length_errors: int
    crc_errors: int
    frame_errors: int
    missed_errors: int

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True, eq=True)
class IpTxStats(IpStats):
    carrier_errors: int
    collisions: int
    aborted_errors: int
    window_errors: int
    heartbeat_errors: int
    carrier_changes: int

##############################


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True, eq=True)
class TcTxQueueConf():
    handle: str
    #root: bool

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True, eq=True)
class TcTxQueueStats(Stats):
    bytes: int
    packets: int
    drops: int
    overlimits: int
    requeues: int
    backlog: int
    qlen: int

@dataclass(frozen=True, eq=True)
class TcTxQueue():
    conf: TcTxQueueConf
    stat: TcTxQueueStats

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True, eq=True)
class CodelTxQueueConf(TcTxQueueConf):
    limit: int
    flows: int
    quantum: int
    target: int
    interval: int
    memory_limit: int
    ecn: bool

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True, eq=True)
class CodelTxQueueStats(TcTxQueueStats):
    maxpacket: int
    drop_overlimit: int
    new_flow_count: int
    ecn_mark: int
    new_flows_len: int
    old_flows_len: int

###############################

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True, eq=True)
class NetIpStats(Stats):
    Forwarding: int
    total_packets_received: int
    with_invalid_addresses: int
    forwarded: int
    incoming_packets_discarded: int
    incoming_packets_delivered: int
    requests_sent_out: int
    outgoing_packets_dropped: int
    dropped_because_of_missing_route: int
    reassemblies_required: int
    packets_reassembled_ok: int
    fragments_received_ok: int
    fragments_created: int

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True, eq=True)
class NetUdpStats(Stats):
    packets_received: int
    packets_to_unknown_port_received: int
    packet_receive_errors: int
    packets_sent: int
    receive_buffer_errors: int
    send_buffer_errors: int
    IgnoredMulti: int

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass(frozen=True, eq=True)
class NetTcpStats():
    Tcp: Dict[str, Any]
    TcpExt: Dict[str, Any]

@dataclass(frozen=True, eq=True)
class NetStats(Stats):
    ip: NetIpStats
    udp: NetUdpStats
    tcp: NetTcpStats

###############################


@dataclass(frozen=True, eq=True)
class TrafficInfoSample():
    timestamp: int
    ip_conf: IpConf
    ip_stats: Tuple[IpRxStats,IpTxStats]
    tc_queues: List[TcTxQueue]
    ns_stats: NetStats


json_str = "{\"ip\": [{\"ifindex\": \"2\", \"ifname\": \"eth0\", \"flags\": [\"BROADCAST\", \"MULTICAST\", \"UP\", \"LOWER_UP\"], \"mtu\": 1500, \"qdisc\": \"mq\", \"operstate\": \"UP\", \"linkmode\": \"DEFAULT\", \"group\": \"default\", \"txqlen\": 1000, \"link_type\": \"ether\", \"address\": \"dc:a6:32:bf:53:b8\", \"broadcast\": \"ff:ff:ff:ff:ff:ff\", \"stats64\": {\"rx\": {\"bytes\": 33360419639, \"packets\": 23864715, \"errors\": 363, \"dropped\": 5, \"over_errors\": 0, \"multicast\": 1564794, \"length_errors\": 0, \"crc_errors\": 0, \"frame_errors\": 0, \"fifo_errors\": 0, \"missed_errors\": 363}, \"tx\": {\"bytes\": 22859809680, \"packets\": 15255003, \"errors\": 0, \"dropped\": 0, \"carrier_errors\": 0, \"collisions\": 0, \"aborted_errors\": 0, \"fifo_errors\": 0, \"window_errors\": 0, \"heartbeat_errors\": 0, \"carrier_changes\": 131}}}], \"tc\": [{\"kind\": \"mq\", \"handle\": \"0:\", \"root\": true, \"options\": {}, \"bytes\": 22859809680, \"packets\": 15255003, \"drops\": 0, \"overlimits\": 0, \"requeues\": 1644322, \"backlog\": 0, \"qlen\": 0}, {\"kind\": \"fq_codel\", \"handle\": \"0:\", \"parent\": \":5\", \"options\": {\"limit\": 10240, \"flows\": 1024, \"quantum\": 1514, \"target\": 4999, \"interval\": 99999, \"memory_limit\": 33554432, \"ecn\": true}, \"bytes\": 9705124999, \"packets\": 6460522, \"drops\": 0, \"overlimits\": 0, \"requeues\": 623700, \"backlog\": 0, \"qlen\": 0, \"maxpacket\": 1514, \"drop_overlimit\": 0, \"new_flow_count\": 198398, \"ecn_mark\": 0, \"new_flows_len\": 0, \"old_flows_len\": 0}, {\"kind\": \"fq_codel\", \"handle\": \"0:\", \"parent\": \":4\", \"options\": {\"limit\": 10240, \"flows\": 1024, \"quantum\": 1514, \"target\": 4999, \"interval\": 99999, \"memory_limit\": 33554432, \"ecn\": true}, \"bytes\": 108855, \"packets\": 1535, \"drops\": 0, \"overlimits\": 0, \"requeues\": 1, \"backlog\": 0, \"qlen\": 0, \"maxpacket\": 590, \"drop_overlimit\": 0, \"new_flow_count\": 2, \"ecn_mark\": 0, \"new_flows_len\": 0, \"old_flows_len\": 0}, {\"kind\": \"fq_codel\", \"handle\": \"0:\", \"parent\": \":3\", \"options\": {\"limit\": 10240, \"flows\": 1024, \"quantum\": 1514, \"target\": 4999, \"interval\": 99999, \"memory_limit\": 33554432, \"ecn\": true}, \"bytes\": 13129459251, \"packets\": 8738085, \"drops\": 0, \"overlimits\": 0, \"requeues\": 1020621, \"backlog\": 0, \"qlen\": 0, \"maxpacket\": 1514, \"drop_overlimit\": 0, \"new_flow_count\": 274186, \"ecn_mark\": 0, \"new_flows_len\": 0, \"old_flows_len\": 0}, {\"kind\": \"fq_codel\", \"handle\": \"0:\", \"parent\": \":2\", \"options\": {\"limit\": 10240, \"flows\": 1024, \"quantum\": 1514, \"target\": 4999, \"interval\": 99999, \"memory_limit\": 33554432, \"ecn\": true}, \"bytes\": 4615, \"packets\": 69, \"drops\": 0, \"overlimits\": 0, \"requeues\": 0, \"backlog\": 0, \"qlen\": 0, \"maxpacket\": 0, \"drop_overlimit\": 0, \"new_flow_count\": 0, \"ecn_mark\": 0, \"new_flows_len\": 0, \"old_flows_len\": 0}, {\"kind\": \"fq_codel\", \"handle\": \"0:\", \"parent\": \":1\", \"options\": {\"limit\": 10240, \"flows\": 1024, \"quantum\": 1514, \"target\": 4999, \"interval\": 99999, \"memory_limit\": 33554432, \"ecn\": true}, \"bytes\": 25111960, \"packets\": 54792, \"drops\": 0, \"overlimits\": 0, \"requeues\": 0, \"backlog\": 0, \"qlen\": 0, \"maxpacket\": 0, \"drop_overlimit\": 0, \"new_flow_count\": 0, \"ecn_mark\": 0, \"new_flows_len\": 0, \"old_flows_len\": 0}], \"num_queue\": {\"num_rx_queues\": \"1\", \"num_tx_queues\": \"5\"}, \"netstat\": {\"Ip\": {\"Forwarding\": \"1\", \"total_packets_received\": \"27836548\", \"with_invalid_addresses\": \"2\", \"forwarded\": \"64\", \"incoming_packets_discarded\": \"0\", \"incoming_packets_delivered\": \"6366993\", \"requests_sent_out\": \"5924282\", \"outgoing_packets_dropped\": \"37\", \"dropped_because_of_missing_route\": \"1\", \"fragments_dropped_after_timeout\": \"97\", \"reassemblies_required\": \"22081167\", \"packets_reassembled_ok\": \"611742\", \"packet_reassemblies_failed\": \"1385952\", \"fragments_received_ok\": \"451288\", \"fragments_created\": \"15189174\"}, \"Icmp\": {\"ICMP messages received\": \"54608\", \"input ICMP message failed\": \"27271\", \"ICMP input histogram\": \"\", \"destination unreachable\": \"54598\", \"echo requests\": \"10\", \"echo replies\": \"2\", \"ICMP messages sent\": \"54635\", \"ICMP messages failed\": \"0\", \"ICMP output histogram\": \"\", \"time exceeded\": \"25\"}, \"IcmpMsg\": {\"InType0\": \"5\", \"InType3\": \"54601\", \"InType8\": \"2\", \"OutType0\": \"2\", \"OutType3\": \"54598\", \"OutType8\": \"10\", \"OutType11\": \"25\"}, \"Tcp\": {\"active connection openings\": \"149701\", \"passive connection openings\": \"122373\", \"failed connection attempts\": \"27280\", \"connection resets received\": \"52\", \"connections established\": \"1\", \"segments received\": \"2977197\", \"segments sent out\": \"3090409\", \"segments retransmitted\": \"27524\", \"bad segments received\": \"1\", \"resets sent\": \"512\"}, \"Udp\": {\"packets_received\": \"2915067\", \"packets_to_unknown_port_received\": \"56\", \"packet_receive_errors\": \"160454\", \"packets_sent\": \"2915449\", \"receive_buffer_errors\": \"160454\", \"send_buffer_errors\": \"17\", \"IgnoredMulti\": \"259611\"}, \"UdpLite\": {}, \"TcpExt\": {\"packets pruned from receive queue because of socket buffer overrun\": \"645\", \"TCP sockets finished time wait in fast timer\": \"121769\", \"delayed acks sent\": \"19080\", \"delayed acks further delayed because of locked socket\": \"3\", \"Quick ack mode was activated 56 times\": \"\", \"packet headers predicted\": \"1366105\", \"acknowledgments not containing data payload received\": \"530414\", \"predicted acknowledgments\": \"546188\", \"Detected reordering 7 times using SACK\": \"\", \"TCPLostRetransmit\": \"144\", \"TCPTimeouts\": \"82009\", \"TCPLossProbes\": \"50\", \"TCPLossProbeRecovery\": \"10\", \"packets collapsed in receive queue due to low socket buffer\": \"36086\", \"TCPBacklogCoalesce\": \"560\", \"TCPDSACKOldSent\": \"56\", \"TCPDSACKRecv\": \"11\", \"connections reset due to unexpected data\": \"105\", \"connections reset due to early user close\": \"47\", \"TCPDSACKIgnoredNoUndo\": \"11\", \"TCPSackShiftFallback\": \"9\", \"TCPBacklogDrop\": \"723\", \"TCPRcvCoalesce\": \"62772\", \"TCPOFOQueue\": \"7630\", \"TCPChallengeACK\": \"1\", \"TCPSYNChallenge\": \"1\", \"TCPSpuriousRtxHostQueues\": \"54535\", \"TCPAutoCorking\": \"1304\", \"TCPFromZeroWindowAdv\": \"2\", \"TCPToZeroWindowAdv\": \"2\", \"TCPWantZeroWindowAdv\": \"18402\", \"TCPSynRetrans\": \"27392\", \"TCPOrigDataSent\": \"1363038\", \"TCPHystartTrainDetect\": \"19\", \"TCPHystartTrainCwnd\": \"350\", \"TCPKeepAlive\": \"4\", \"TCPDelivered\": \"1484764\", \"TCPAckCompressed\": \"2301\"}, \"IpExt\": {\"InNoRoutes\": \"64\", \"OutMcastPkts\": \"6\", \"InBcastPkts\": \"259611\", \"InOctets\": \"34597609213\", \"OutOctets\": \"23148746241\", \"OutMcastOctets\": \"240\", \"InBcastOctets\": \"84612289\", \"InNoECTPkts\": \"27836548\"}}, \"timestamp\": \"1636128221889074932\"}"
#"

#print(json_str)
main_dict = json.loads(json_str)
main_dict['ip'][0]
ip_conf = IpConf.from_dict(main_dict['ip'][0])
ip_rx_stats = IpRxStats.from_dict(main_dict['ip'][0]['stats64']['rx'])
ip_tx_stats = IpTxStats.from_dict(main_dict['ip'][0]['stats64']['tx'])

tc_q_list = []
for item in main_dict['tc']:
    if(item['kind'] == "fq_codel"):
        item = {**item['options'], **item}
        item.pop('options',None)
        tc_q_conf = CodelTxQueueConf.from_dict(item)
        tc_q_stat = CodelTxQueueStats.from_dict(item)
    else:
        tc_q_conf = TcTxQueueConf.from_dict(item)
        tc_q_stat = TcTxQueueStats.from_dict(item)
    
    tc_q_list.append(TcTxQueue(conf=tc_q_conf,stat=tc_q_stat))

net_ip = NetIpStats.from_dict(main_dict['netstat']['Ip'])
net_udp = NetUdpStats.from_dict(main_dict['netstat']['Udp'])
net_tcp = NetTcpStats.from_dict(main_dict['netstat'])
ns_stats = NetStats(ip=net_ip,udp=net_udp,tcp=net_tcp)

timestamp = int(main_dict['timestamp'])

sample = TrafficInfoSample(timestamp=timestamp,ip_conf=ip_conf,ip_stats=(ip_rx_stats,ip_tx_stats),tc_queues=tc_q_list,ns_stats=ns_stats)
#print(sample)
pprint(sample)
