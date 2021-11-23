# miscellaneous utility functions and classes
import threading
from contextlib import contextmanager
from typing import Callable, Dict, Generator, Optional, Tuple

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
