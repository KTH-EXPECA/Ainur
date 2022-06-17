from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .resources import ResourceCollection, SwitchResource, WorkloadHostResource


class Testbed:
    def __init__(self, resources: ResourceCollection):
        # build in-memory resources from static resource collection
        pass

    def configure_vlan(
        self,
        switch: str,
        vlan_id: Optional[int] = None,
        vlan_name: Optional[str] = None,
    ):
        pass
