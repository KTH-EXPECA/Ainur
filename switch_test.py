from ipaddress import IPv4Interface
from pathlib import Path

from ainur import *


if __name__ == '__main__':
    # quick test to verify network + swarm work

    # bring up the network
    with ManagedSwitch('glorfindel', ('cisco','expeca'), IPv4Interface('192.168.1.5/24'), 5, quiet=False) as switch:
        #switch.make_vlan(ports=[31,32,33],name='test1')
        #switch.make_vlan(ports=[21,20],name='test2')
        #switch.make_vlan(ports=[34,28,22],name='test3')
        #switch.make_vlan(ports=[11,13],name='test4')
        #switch.make_vlan(ports=[10,12],name='test5')
        switch.remove_vlan(id_num=4)
