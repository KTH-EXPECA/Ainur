from __future__ import annotations

import re
from dataclasses import dataclass

from contextlib import AbstractContextManager
from ipaddress import IPv4Interface, IPv4Network
from typing import FrozenSet, Mapping
from operator import attrgetter

import ansible_runner
from loguru import logger

from .ansible import AnsibleContext
from .hosts import WorkloadHost,AnsibleHost,ConnectedWorkloadInterface,WorkloadInterface,Wire,SoftwareDefinedWiFiRadio,WiFiRadio,Phy,SwitchConnection


import pexpect

@dataclass(frozen=True, eq=True)
class Vlan():
    default: bool
    name: str
    id_num: int
    switch_name: str
    ports: list[int]

class ManagedSwitch(AbstractContextManager):
    """
    Represents a managed network switch.

    Can be used as a context manager for easy vlan deployment on a managed switch 
    and automatic teardown of vlans.
    """

    def __init__(self,
                 name: str,
                 credentials: Tuple[str,str],
                 address: IPv4Interface,
                 timeout: int,
                 quiet: bool = True):

        logger.info('Contacting the network switch.')

        #Second argument is assigned to the variable user
        user = credentials[0]
        #Third argument is assigned to the variable password
        password = credentials[1]


        #This spawns the telnet program and connects it to the variable name
        child = pexpect.spawn("telnet %s" % name, timeout=timeout)

        #The script expects login
        child.expect_exact("Username:")
        child.send(user+"\n")

        #The script expects Password
        child.expect_exact("Password:")
        child.send(password+"\n")

        child.expect_exact(name+"#")
        
        self._child = child
        self._name = name
        self._credentials = credentials
        self._address = address
        self._timeout = timeout
        self._quiet = quiet

        #self.hard_remove_vlan(id_num=4)
        
        self.update_vlans()

        

    @property
    def vlans(self) -> FrozenSet[Vlan]:
        return frozenset(self._vlans)
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def credentials(self) -> Tuple[str,str]:
        return self._credentials

    @property
    def address(self) -> IPv4Network:
        return self._address
    
    @property
    def timeout(self) -> int:
        return self._timeout


    def update_vlans(self):

        vlans = []
        child = self._child
        
        child.send("show vlan\n")

        child.send("configure terminal\n")
        child.expect_exact(self._name+'(config)#')

        lines = child.before.splitlines()

        del lines[0]  # delete first 4 lines
        del lines[-2:]  # delete last 4 lines

        #log
        if not self._quiet:
            for item in lines:
                print(item.decode("utf-8"))

        del lines[0:3]  # delete first 4 lines

        # log
        if not self._quiet:
            print('Number of vlans: %d' % len(lines))

        for idx, line in enumerate(lines):
            line = line.decode('utf-8')
            result = [x.strip() for x in line.split('|')]
            vlan_id = int(result[0])
            vlan_name = result[1]
            ports_str = re.sub("[^0-9-]", " ", result[2])
            vlan_ports = []
            for vlp in ports_str.split():
                if '-' not in vlp:
                    vlan_ports.append(int(vlp))
                else:
                    nums = vlp.split('-')
                    vlan_ports.extend([n for n in range(int(nums[0]),int(nums[1])+1)])

            vlans.append(Vlan(name=vlan_name,id_num=vlan_id,ports=vlan_ports,switch_name=self._name, default=True))
            if not self._quiet:
                print('Vlan #%d id: %d, name: %s, ports: %s' % (idx,vlan_id,vlan_name,vlan_ports))#If it all goes pear shaped the script will timeout after 20 seconds.
        
        self._vlans = vlans
        logger.info('Default vlans loaded.')


    def make_vlan(self, ports: List[int], name: str) -> Vlan:

        # to get the object with the characteristic (max id)
        biggest_vlan_id = max(self._vlans, key=attrgetter("id_num"))
        vlanid = biggest_vlan_id.id_num+1

        child = self._child

        child.send("vlan %d\n" % vlanid)

        child.expect_exact(self._name+"(config-vlan)#")
        child.send("name %s\n" % name)

        child.expect_exact(self._name+"(config-vlan)#")
        child.send("exit\n")

        for portnum in ports:

            child.expect_exact(self._name+"(config)#")
            child.send("interface gi%d\n" % portnum)

            child.expect_exact(self._name+"(config-if)")
            child.send("switchport mode access\n")

            child.expect_exact(self._name+"(config-if)")
            child.send("switchport access vlan %d\n" % vlanid)

            child.expect_exact(self._name+"(config-if)")
            child.send("exit\n")
            
        child.expect_exact(self._name+'(config)#')

        new_vlan = Vlan(name=name,id_num=vlanid,ports=ports,switch_name=self._name, default=False)
        self._vlans.append(new_vlan)
        logger.info('New vlan with id: %d added.'% vlanid)
        return new_vlan
    
    def hard_remove_vlan(self,id_num: int):

        child = self._child
        
        child.send("configure terminal\n")
        child.expect_exact(self._name+'(config)#')

        child.send("no vlan %d\n" % id_num)
        child.expect_exact(self._name+"(config)")

        logger.warning('Workload switch vlan with id: %d is removed.' % id_num)

    def remove_vlan(self, id_num: int):
        vlan = [ vl for vl in self._vlans if vl.id_num == id_num ]
        if len(vlan) == 0:
            logger.error('There is no vlan with id: %d to be removed.' % id_num)
            return
        vlan = vlan[0]

        child = self._child
        child.send("no vlan %d\n" % id_num)
        child.expect_exact(self._name+"(config)")

        self._vlans.remove(vlan)
        logger.warning('Workload switch vlan with id: %d is removed.' % id_num)
        

    def tear_down(self) -> None:
        """
        Removes all the added vlans.
        Note that after calling this method, this object will be left in an
        invalid state and should not be used any more.
        """
        logger.warning('Removing workload switch vlans.')
        child = self._child
    
        non_defalut_vlan_ids = [ vl.id_num for vl in self._vlans if vl.default == False]
        # remove all non default vlans
        for nd_id_num in non_defalut_vlan_ids:
            self.remove_vlan(nd_id_num)

        child.send("exit\n")
        child.send("exit\n")
        child.send("exit\n")
        child.send("exit\n")
        child.expect(pexpect.EOF)
        logger.warning('Workload switch non default vlans removed.')

    def __enter__(self) -> ManagedSwitch:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(ManagedSwitch, self).__exit__(exc_type, exc_val, exc_tb)
