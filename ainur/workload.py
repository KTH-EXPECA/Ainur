from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any, FrozenSet

from frozendict import frozendict


@dataclass(frozen=True, eq=True)
class WorkloadServiceDefinition:
    name: str
    image: str
    placement: frozendict[str, Any]
    environment: frozendict[str, Any] = field(default_factory=frozendict)


@dataclass(frozen=True, eq=True)
class WorkloadDefinition:
    name: str
    services: frozendict[WorkloadServiceDefinition, int]
    max_duration: str = '1d'

    # TODO include fluentbit container here somewhere?


@dataclass(frozen=True, eq=True)
class RunningWorkloadService:
    definition: WorkloadServiceDefinition
    service_id: str
    swarm_id: str
    start_time: datetime.datetime = field(default_factory=datetime.datetime.now)


@dataclass(frozen=True, eq=True)
class RunningWorkload:
    definition: WorkloadDefinition
    services: FrozenSet[RunningWorkloadService]
    swarm_id: str
    workload_id: uuid.UUID = field(default_factory=uuid.uuid4, init=False)
    start_time: datetime.datetime = field(
        default_factory=datetime.datetime.now, init=False)
