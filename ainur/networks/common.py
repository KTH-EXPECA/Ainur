#  Copyright (c) 2022 KTH Royal Institute of Technology, Sweden,
#  and the ExPECA Research Group (PI: Prof. James Gross).
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from __future__ import annotations

import abc
from contextlib import AbstractContextManager, ExitStack
from types import TracebackType
from typing import Any, Iterator, List, Mapping, Type, TypeVar, overload

from ..hosts import AinurHost


class Layer3Error(Exception):
    pass


class Layer3Network(AbstractContextManager, Mapping[str, AinurHost]):

    @abc.abstractmethod
    def __iter__(self) -> Iterator[str]:
        pass

    @abc.abstractmethod
    def __getitem__(self, item: str) -> AinurHost:
        pass

    @abc.abstractmethod
    def __len__(self) -> int:
        pass

    @abc.abstractmethod
    def __contains__(self, item: Any) -> bool:
        pass

    @abc.abstractmethod
    def __enter__(self) -> Layer3Network:
        pass

    @overload
    def __exit__(self, exc_type: None, exc_val: None, exc_tb: None) -> None:
        ...

    @overload
    def __exit__(
            self,
            exc_type: Type[BaseException],
            exc_val: BaseException,
            exc_tb: TracebackType,
    ) -> None:
        ...

    def __exit__(
            self,
            exc_type: Type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
    ) -> None:
        self.tear_down()
        return super(Layer3Network, self).__exit__(exc_type, exc_val, exc_tb)

    @abc.abstractmethod
    def tear_down(self) -> None:
        pass


_NL = TypeVar('_NL', bound=Layer3Network)
"""Typevar to indicate that add_network() returns same type as argument"""


class CompositeLayer3Network(Layer3Network):
    def __init__(self):
        super(CompositeLayer3Network, self).__init__()
        self._stack = ExitStack()
        self._networks: List[Layer3Network] = []

    def add_network(self, net: _NL) -> _NL:
        """

        Parameters
        ----------
        net

        Returns
        -------
            The added network, for chaining constructors
        """
        self._networks.append(net)
        return net

    def __enter__(self):
        with self._stack:
            for net in self._networks:
                self._stack.enter_context(net)

            self._stack = self._stack.pop_all()
        return self

    def tear_down(self) -> None:
        self._stack.close()
        self._stack = ExitStack()
        self._networks.clear()

    def __iter__(self) -> Iterator[str]:
        for net in self._networks:
            for hostname in net:
                yield hostname

    def __getitem__(self, item: str) -> AinurHost:
        for net in self._networks:
            try:
                return net[item]
            except KeyError:
                continue

        raise KeyError(item)

    def __len__(self) -> int:
        return sum(map(len, self._networks))

    def __contains__(self, item: Any) -> bool:
        try:
            _ = self[item]
            return True
        except KeyError:
            return False


def verify_wkld_net_connectivity(network: Layer3Network) -> None:
    # TODO: implement this using Docker and just pinging all workload addresses.
    pass
