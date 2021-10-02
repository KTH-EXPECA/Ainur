from dataclasses import dataclass


@dataclass(frozen=True, eq=True)
class ServerWorkload:
    name: str
    image: str


@dataclass(frozen=True, eq=True)
class ClientWorkload:
    name: str
    image: str


@dataclass(frozen=True, eq=True)
class Workload:
    name: str
    server: ServerWorkload
    client: ClientWorkload
