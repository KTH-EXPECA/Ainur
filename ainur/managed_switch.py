from __future__ import annotations

import json
import re
from collections import defaultdict
from contextlib import AbstractContextManager
from dataclasses import dataclass
from ipaddress import IPv4Interface
from operator import attrgetter
from typing import FrozenSet, List, Tuple

import pexpect
from loguru import logger

from .hosts import LTE, WiFi, Wire


@dataclass(frozen=True, eq=True)
class Vlan:
    default: bool
    name: str
    id_num: int
    switch_name: str
    ports: list[int]


class ManagedSwitch(AbstractContextManager):
    """
    Represents a managed network switch.

    Can be used as a context manager for easy vlan deployment on a managed
    switch
    and automatic teardown of vlans.
    """

    def __init__(self,
                 name: str,
                 credentials: Tuple[str, str],
                 address: IPv4Interface,
                 timeout: int,
                 quiet: bool = True):

        # we do login - logout for every command since there is a timeout for
        # each login session on the cisco switch

        self._name = name
        self._address = address
        self._timeout = timeout
        # self._quiet = quiet

        # Second argument is assigned to the variable user
        self._user = credentials[0]
        # Third argument is assigned to the variable password
        self._password = credentials[1]

        logger.info('Contacting the network switch.')

        # update vlans table
        self.update_vlans()

    @property
    def vlans(self) -> FrozenSet[Vlan]:
        return frozenset(self._vlans)

    @property
    def name(self) -> str:
        return self._name

    # @property
    # def credentials(self) -> Tuple[str, str]:
    #     return self._credentials
    #
    # @property
    # def address(self) -> IPv4Network:
    #     return self._address

    @property
    def timeout(self) -> int:
        return self._timeout

    def login(self):

        # This spawns the telnet program and connects it to the variable name
        child = pexpect.spawn("telnet %s" % self._name, timeout=self._timeout)

        # The script expects login
        child.expect_exact("Username:")
        child.send(self._user + "\n")

        # The script expects Password
        child.expect_exact("Password:")
        child.send(self._password + "\n")

        child.expect_exact(self._name + "#")

        # telnet connection is ready
        return child

    # noinspection PyMethodMayBeStatic
    def logout(self, child):

        # assume we are in login state
        child.send("exit\n")
        child.send("exit\n")
        child.expect(pexpect.EOF)

    def make_connections(self, inventory, conn_specs):

        workload_hosts = inventory['hosts']
        radios = inventory['radios']
        radiohosts = inventory['radiohosts']

        # Make workload switch vlans
        ports_wirednets = {}
        for host_name in conn_specs.keys():
            for if_name in conn_specs[host_name].keys():
                phy = conn_specs[host_name][if_name].phy
                interface = workload_hosts[host_name].interfaces[if_name]
                # TODO: isinstance check
                if isinstance(phy, WiFi):
                    # WiFi sdr vlans
                    if phy.radio != 'native':
                        host_port = interface.switch_connection.port
                        ports = [host_port,
                                 radios[phy.radio].switch_connection.port]
                        vlan_name = workload_hosts[host_name].ansible_host \
                                    + '_to_' + phy.radio
                        self.make_vlan(ports=ports, name=vlan_name)
                elif isinstance(phy, Wire):
                    # wired nodes vlans
                    # connect the ones with the same network name
                    ports_wirednets[
                        interface.switch_connection.port] = phy.network
                elif isinstance(phy, LTE):
                    # LTE nodes vlans
                    # connect the host to its radiohost
                    host_port = interface.switch_connection.port
                    ports = [host_port,
                                 radiohosts[phy.radio_host].interfaces[phy.radio_host_data_interface].switch_connection.port]
                    vlan_name = workload_hosts[host_name].ansible_host \
                                    + '_to_' + phy.radio_host
                    self.make_vlan(ports=ports, name=vlan_name)

        # Grouping dictionary by values and make lists of ports for each
        # network name
        wired_nets = defaultdict(list)
        for key, value in sorted(ports_wirednets.items()):
            wired_nets[value].append(key)

        for wired_net_name, ports_list in wired_nets.items():
            self.make_vlan(ports=ports_list, name=wired_net_name)

    def update_vlans(self):
        logger.debug('Updating VLANs.')
        child = self.login()

        vlans = []
        child.send("show vlan\n")

        # go to config mode (necessary for having one line after the table)
        child.send("configure terminal\n")
        child.expect_exact(self._name + '(config)#')

        lines = child.before.splitlines()

        # TODO: del is not a good thing to do in python
        # del lines[0]  # delete first 4 lines
        # del lines[-2:]  # delete last 4 lines
        lines = lines[1:-2]

        # log
        # if not self._quiet:
        #     for item in lines:
        #         print(item.decode("utf-8"))
        for item in lines:
            logger.debug(item.decode('utf-8'))

        del lines[0:3]  # delete first 4 lines

        # log
        # if not self._quiet:
        # print('Number of vlans: %d' % len(lines))
        logger.debug(f'Number of vlans: {len(lines)}')

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
                    vlan_ports.extend(
                        [n for n in range(int(nums[0]), int(nums[1]) + 1)])

            vlans.append(Vlan(name=vlan_name, id_num=vlan_id, ports=vlan_ports,
                              switch_name=self._name, default=True))
            # if not self._quiet:
            #     print('Vlan #%d id: %d, name: %s, ports: %s' % (idx,
            #     vlan_id,vlan_name,vlan_ports))
            #     #If it all goes pear shaped the script will timeout after
            #     20 seconds.
            logger.debug('VLAN:\n' + json.dumps({
                'index': idx,
                'id'   : vlan_id,
                'name' : vlan_name,
                'ports': vlan_ports
            }, indent=4))

        self._vlans = vlans

        # go back to login mode
        child.send("exit\n")
        child.expect_exact(self._name + "#")

        self.logout(child)

        logger.info('Default vlans loaded.')

    def make_vlan(self, ports: List[int], name: str) -> Vlan:

        # to get the object with the characteristic (max id)
        if len(self._vlans) != 0:
            biggest_vlan_id = max(self._vlans, key=attrgetter("id_num"))
            vlanid = biggest_vlan_id.id_num + 1
        else:
            vlanid = 2

        child = self.login()

        # go to config mode
        child.send("configure terminal\n")
        child.expect_exact(self._name + '(config)#')

        child.send("vlan %d\n" % vlanid)

        child.expect_exact(self._name + "(config-vlan)#")
        child.send("name %s\n" % name)

        child.expect_exact(self._name + "(config-vlan)#")
        child.send("exit\n")

        for portnum in ports:
            child.expect_exact(self._name + "(config)#")
            child.send("interface gi%d\n" % portnum)

            child.expect_exact(self._name + "(config-if)")
            child.send("switchport mode access\n")

            child.expect_exact(self._name + "(config-if)")
            child.send("switchport access vlan %d\n" % vlanid)

            child.expect_exact(self._name + "(config-if)")
            child.send("exit\n")

        child.expect_exact(self._name + '(config)#')

        # go back to login mode
        child.send("exit\n")
        child.expect_exact(self._name + "#")

        new_vlan = Vlan(name=name, id_num=vlanid, ports=ports,
                        switch_name=self._name, default=False)
        self._vlans.append(new_vlan)
        logger.info('New vlan with id: %d added.' % vlanid)
        return new_vlan

    def hard_remove_vlan(self, id_num: int):

        child = self.login()

        # go to config mode
        child.send("configure terminal\n")
        child.expect_exact(self._name + '(config)#')

        # remove it
        child.send("no vlan %d\n" % id_num)
        child.expect_exact(self._name + "(config)")

        # go back to login mode
        child.send("exit\n")
        child.expect_exact(self._name + "#")

        self.logout(child)

        logger.warning('Workload switch vlan with id: %d is removed.' % id_num)

    def remove_vlan(self, id_num: int):
        vlan = [vl for vl in self._vlans if vl.id_num == id_num]
        if len(vlan) == 0:
            logger.error('There is no vlan with id: %d to be removed.' % id_num)
            return
        vlan = vlan[0]

        child = self.login()

        # go to config mode
        child.send("configure terminal\n")
        child.expect_exact(self._name + '(config)#')

        # remove it
        child.send("no vlan %d\n" % id_num)
        child.expect_exact(self._name + "(config)")

        # go back to login mode
        child.send("exit\n")
        child.expect_exact(self._name + "#")

        self._vlans.remove(vlan)
        logger.warning('Workload switch vlan with id: %d is removed.' % id_num)

    def tear_down(self) -> None:
        """
        Removes all the added vlans.
        Note that after calling this method, this object will be left in an
        invalid state and should not be used any more.
        """
        logger.warning('Removing workload switch vlans.')

        non_defalut_vlan_ids = [vl.id_num for vl in self._vlans if
                                vl.default == False]
        # remove all non default vlans
        for nd_id_num in non_defalut_vlan_ids:
            self.remove_vlan(nd_id_num)

        logger.warning('Workload switch non default vlans removed.')

    def __enter__(self) -> ManagedSwitch:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.tear_down()
        return super(ManagedSwitch, self).__exit__(exc_type, exc_val, exc_tb)
