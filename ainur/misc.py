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

# miscellaneous utility functions and classes
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Callable, Dict, Generator, NamedTuple, Optional, Tuple

from docker import DockerClient


@contextmanager
def docker_client_context(*args, **kwargs) \
        -> Generator[DockerClient, None, None]:
    """
    Utility context manager which simply creates a DockerClient with the
    provided arguments, binds it to the 'as' argument, and makes sure to
    close it on exiting the context.

    Parameters
    ----------
    args

    kwargs

    Yields
    ------
    DockerClient
        An initialized Docker client instance.
    """
    client = DockerClient(*args, **kwargs)
    yield client
    client.close()


def ceildiv(a: int, b: int) -> int:
    """
    Ceiling division, such that c = a/b is rounded to the next whole integer.
    """

    # ceil(a/b) = -(a // -b), see https://stackoverflow.com/a/17511341
    return -(a // -b)


class HMS(NamedTuple):
    hours: int | float
    minutes: int | float
    seconds: int | float

    def __str__(self):
        return f'{self.hours}h {self.minutes}m {self.seconds}s'


def seconds2hms(seconds: int | float) -> HMS:
    """
    Convert a value in seconds to total hours, minutes, and seconds.

    Parameters
    ----------
    seconds

    Returns
    -------
    Tuple
        An (hours, minutes, seconds) tuple.
    """
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)

    return HMS(h, m, s)


class RepeatingTimer(threading.Timer):
    """
    Repeats until cancelled or the internal function returns false.
    """

    def __init__(self,
                 interval: float,
                 function: Callable[..., bool],
                 args: Optional[Tuple] = None,
                 kwargs: Optional[Dict] = None):
        super(RepeatingTimer, self).__init__(interval=interval,
                                             function=function,
                                             args=args,
                                             kwargs=kwargs)

    # noinspection PyUnresolvedReferences
    def run(self):
        self.finished.wait(self.interval)
        while not self.finished.is_set() \
                and self.function(*self.args, **self.kwargs):
            self.finished.wait(self.interval)
        self.finished.set()
