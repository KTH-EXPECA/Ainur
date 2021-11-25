from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from dataclasses import asdict
from dataclasses_json import dataclass_json
from dataclasses_json import Undefined
from dacite import from_dict

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
    parent: str
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
    forwarded: int
    incoming_packets_discarded: int
    incoming_packets_delivered: int
    requests_sent_out: int
    outgoing_packets_dropped: int
    fragments_received_ok: int = -1
    fragments_created: int = -1
    packets_reassembled_ok: int = -1
    reassemblies_required: int = -1
    dropped_because_of_missing_route: int = -1
    with_invalid_addresses: int = -1

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
    host: str
    timestamp: int
    ip_conf: IpConf
    ip_stats: Tuple[IpRxStats,IpTxStats]
    tc_queues: List[TcTxQueue]
    ns_stats: NetStats

    def __sub__(self, other):
        assert self.host == other.host
        
        new_host = self.host
        new_timestamp = self.timestamp-other.timestamp
        new_ip_conf = self.ip_conf
        new_ip_stats = (self.ip_stats[0]-other.ip_stats[0],self.ip_stats[1]-other.ip_stats[1])
        new_tc_queues = []
        for idx,self_tc_queue in enumerate(self.tc_queues):
            new_tc_queues.append(TcTxQueue(conf=self_tc_queue.conf,stat=self_tc_queue.stat-other.tc_queues[idx].stat))
        new_ns_stats = NetStats(ip=self.ns_stats.ip-other.ns_stats.ip,udp=self.ns_stats.udp-other.ns_stats.udp,tcp=self.ns_stats.tcp)

        return TrafficInfoSample(host=new_host, timestamp=new_timestamp, ip_conf=new_ip_conf, ip_stats=new_ip_stats, tc_queues=new_tc_queues, ns_stats=new_ns_stats)

        

