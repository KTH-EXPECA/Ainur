from contextlib import AbstractContextManager
from typing import Iterator, Mapping, Set, Tuple, _T_co

from .hosts import Layer2ConnectedWorkloadHost


class PhysicalLayer(AbstractContextManager,
                    Mapping[str, Layer2ConnectedWorkloadHost]):

    def __len__(self) -> int:
        # TODO: should return the number of hosts in the network
        pass

    def __iter__(self) -> Iterator[str]:
        # TODO: should return an iterator over the host names in the network.
        #  If you're not sure how to do this you can leave it to me once the
        #  rest of the class is done.
        pass

    def __getitem__(self, host_id: str) -> Layer2ConnectedWorkloadHost:
        # TODO: implements the [] operator to look up Layer2 hosts by their
        #  name.
        pass
