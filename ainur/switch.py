from __future__ import annotations

import contextlib
import re
from abc import abstractmethod
from contextlib import AbstractContextManager
from ipaddress import IPv4Interface
from typing import FrozenSet, Iterable, Iterator, NamedTuple, Optional, Tuple

import pexpect
from loguru import logger


class SwitchError(Exception):
    pass


class _VLAN(NamedTuple):
    name: str
    id_num: int
    ports: FrozenSet[int]
    default: bool


class _SwitchBase(AbstractContextManager):
    @abstractmethod
    def add_vlan(
        self,
        name: str,
        ports: Iterable[int],
        id_num: Optional[int] = None,
    ) -> int:
        pass

    @abstractmethod
    def remove_vlan(self, vlan_id: int) -> None:
        pass

    @abstractmethod
    def reset(self) -> None:
        pass


class ManagedSwitch(_SwitchBase):
    _LOGIN_REGEX = r".*#"
    _CONFIG_REGEX = r".*\(config\)#"
    _CFG_VLAN_REGEX = r".*\(config-vlan\)#"
    _CFG_IF_REGEX = r".*\(config-if\)"

    def __init__(
        self,
        address: IPv4Interface,
        username: str,
        password: str,
        timeout: float,
        num_ports: int,
        reserved_ports: Iterable[int] = (),
    ):

        self._address = address

        @contextlib.contextmanager
        def login_context() -> Iterator[pexpect.spawn]:
            # context manager for logging in and logging out during operations
            # This spawns the telnet program and connects it to the variable name
            telnet = pexpect.spawn(f"telnet {address.ip}", timeout=timeout)

            # The script expects login
            telnet.expect_exact("Username:")
            telnet.send(username + "\n")

            # The script expects Password
            telnet.expect_exact("Password:")
            telnet.send(password + "\n")

            # match "<any name>#"
            telnet.expect(self._LOGIN_REGEX)

            # telnet connection is ready
            try:
                yield telnet
            finally:
                telnet.send("exit\n")
                telnet.send("exit\n")
                telnet.expect(pexpect.EOF)

        @contextlib.contextmanager
        def config_context(telnet: pexpect.spawn) -> Iterator[pexpect.spawn]:
            telnet.send("configure terminal\n")
            telnet.expect(self._CONFIG_REGEX)
            try:
                yield telnet
            finally:
                telnet.send("exit\n")
                telnet.expect(self._LOGIN_REGEX)

        self._login_ctx = login_context
        self._config_ctx = config_context

        self._avail_ports = set([i + 1 for i in range(num_ports)]).difference(
            reserved_ports
        )

        self._vlans = {}
        self._vlan_names = set()

        # fetch initial state
        logger.debug("Updating VLANs.")
        with self._login_ctx() as telnet:
            telnet.send("show vlan\n")

            # go to config mode (necessary for having one line after the table)
            with self._config_ctx(telnet) as telnet:

                lines = telnet.before.splitlines()
                lines = lines[1:-2]

                for item in lines:
                    logger.debug(item.decode("utf-8"))

                lines = lines[3:]

                logger.debug(f"Number of vlans: {len(lines)}")

                for idx, line in enumerate(lines):
                    line = line.decode("utf-8")
                    result = [x.strip() for x in line.split("|")]
                    vlan_id = int(result[0])
                    vlan_name = result[1]
                    ports_str = re.sub(r"[^\d-]", " ", result[2])
                    vlan_ports = set()
                    for vlp in ports_str.split():
                        if "-" not in vlp:
                            vlan_ports.add(int(vlp))
                        else:
                            nums = vlp.split("-")
                            vlan_ports.update(
                                [n for n in range(int(nums[0]), int(nums[1]) + 1)]
                            )

                    self._avail_ports.difference_update(vlan_ports)
                    vlan = _VLAN(
                        name=vlan_name,
                        id_num=vlan_id,
                        ports=frozenset(vlan_ports),
                        default=True,
                    )
                    self._vlans[vlan_id] = vlan
                    self._vlan_names.add(vlan.name)

                    logger.debug(f"VLAN: {vlan}")

            logger.info("Default vlans loaded.")

    def add_vlan(
        self,
        name: str,
        ports: Iterable[int],
        id_num: Optional[int] = None,
    ) -> int:
        ports = frozenset(ports)
        if len(self._avail_ports.intersection(ports)) == 0:
            missing = ports.difference(self._avail_ports)

            raise SwitchError(
                f"Cannot create VLAN {name}: ports {missing} are not available."
            )
        elif name in self._vlan_names:
            raise SwitchError(f"A VLAN with name {name} already exists.")
        elif id_num is not None and id_num in self._vlans:
            raise SwitchError(f"A VLAN with id {id_num} already exists.")
        elif id_num is None:
            id_num = max(self._vlans.keys()) + 1

        vlan = _VLAN(name=name, id_num=id_num, ports=ports, default=False)

        logger.debug(f"Creating new VLAN {vlan}.")

        with self._login_ctx() as telnet:
            with self._config_ctx(telnet) as telnet:
                # create the vlan
                telnet.send(f"vlan {id_num:d}\n")

                telnet.expect(self._CFG_VLAN_REGEX)
                telnet.send(f"name {name}\n")

                telnet.expect(self._CFG_VLAN_REGEX)
                telnet.send("exit\n")

                # add the ports
                for portnum in ports:
                    telnet.expect(self._CONFIG_REGEX)
                    telnet.send(f"interface gi{portnum:d}\n")

                    telnet.expect(self._CFG_IF_REGEX)
                    telnet.send("switchport mode access\n")

                    telnet.expect(self._CFG_IF_REGEX)
                    telnet.send(f"switchport access vlan {id_num:d}\n")

                    telnet.expect(self._CFG_IF_REGEX)
                    telnet.send("exit\n")

                telnet.expect(self._CONFIG_REGEX)

        self._vlans[id_num] = vlan
        self._vlan_names.add(vlan.name)
        logger.info(f"New VLAN {vlan} added.")
        return id_num

    def remove_vlan(self, id_num: int):
        try:
            vlan = self._vlans[id_num]
        except KeyError:
            raise SwitchError(f"No VLAN with id {id_num}.")

        if vlan.default:
            raise SwitchError(f"Cannot remove default VLAN {vlan}")

        with self._login_ctx() as telnet:
            with self._config_ctx(telnet) as telnet:
                # remove it
                telnet.send(f"no vlan {vlan.id_num:d}\n")
                telnet.expect(self._CONFIG_REGEX)

        # update internal state
        self._vlans.pop(id_num)
        self._vlan_names.remove(vlan.name)
        self._avail_ports.update(vlan.ports)

        logger.warning(f"VLAN {vlan} has been removed.")

    def reset(self) -> None:
        logger.warning("Removing non-default VLANS")
        vlans = self._vlans.copy()

        for id_num, vlan in vlans:
            if not vlan.default:
                self.remove_vlan(id_num)

    def __enter__(self) -> ManagedSwitch:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.reset()
        return super(ManagedSwitch, self).__exit__(exc_type, exc_val, exc_tb)


if __name__ == "__main__":
    with ManagedSwitch(
        IPv4Interface("192.168.0.2/16"),
        username="cisco",
        password="expeca",
        timeout=30,
        num_ports=48,
        reserved_ports=[1, 3, 4],
    ) as switch:
        vlan_id = switch.add_vlan(name="testvlan", ports=[25, 26, 27])
        input("Press any key to shut down.")
