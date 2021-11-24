from __future__ import annotations

import contextlib
import json
import string
import tempfile
from dataclasses import dataclass, field
from distutils.version import LooseVersion
from enum import Enum, auto
from os import PathLike
from pathlib import Path
from typing import Any, Dict, Generator

import yaml
from compose.config.config import ConfigFile
from dataclasses_json import config, dataclass_json

from .errors import ConfigError

_min_compose_version = LooseVersion('3.0')


def validate_compose_version(compose_spec: Dict[str, Any]) -> None:
    """
    Parameters
    ----------
    compose_spec

    Raises
    ------
    ConfigError
        If compose specification is not at least the minimum required version.
    """
    conf = ConfigFile('compose_spec', compose_spec)
    if not (conf.config_version >= conf.version >= _min_compose_version):
        raise ConfigError('Nested docker-compose specification in workload '
                          f'specification must be at least version '
                          f'{_min_compose_version}.')


@dataclass_json
@dataclass(frozen=True)
class WorkloadSpecification:
    """
    Specification of a Testbed workload.

    In practice this corresponds to a nested, JSON and/or YAML-compatible
    structure:

    .. code-block:: yaml

       ---
       name: WorkloadExample
       author: "Manuel Olguín Muñoz"
       email: "molguin@kth.se"
       version: "1.0a"
       url: "expeca.proj.kth.se"
       max_duration: "3h 30m"
       compose:
          version: "3.9"
          services:
            ...
       ...

    Where `compose` corresponds to a docker-compose v3+ application stack
    specification.
    """

    name: str = field(
        metadata=config(
            # strip any whitespace from the name on load
            decoder=lambda s:
            s.translate(str.maketrans('', '', string.whitespace))
        )
    )
    """
    A descriptive name for this workload.
    Will be stripped of all whitespace on parsing.
    """

    compose: Dict[str, Any] = field()
    """
    A docker-compose specification. 
    Must adhere to version 3.0+ of the docker-compose spec, see 
    https://docs.docker.com/compose/compose-file/compose-file-v3/`.
    """

    author: str = ''
    """
    Author(s) of this workload specification. Optional.
    """

    email: str = ''
    """
    Contact emails for the authors of this workload specification. Optional.
    """

    version: LooseVersion = field(
        default=LooseVersion('1.0'),
        metadata=config(
            decoder=LooseVersion,
            encoder=str
        )
    )
    """
    Version of this workload specification. Optional, defaults to 1.0.
    """

    url: str = ''
    """
    Info url. Optional.
    """

    max_duration: str = '1d'
    """
    Maximum allowed duration for this workload. 
    Optional, defaults to one (1) full day (24 hours).
    """

    @classmethod
    def from_yaml_file(cls, path: PathLike) -> WorkloadSpecification:
        """
        Load a specification from a YAML file.

        Parameters
        ----------
        path
            Filesystem path to the target specification file.

        Returns
        -------
        WorkloadSpecification
            A parsed specification instance.
        """
        with Path(path).open('r') as fp:
            spec = yaml.safe_load(fp)

        return WorkloadSpecification.from_dict(spec)

    @contextlib.contextmanager
    def temp_compose_file(self) -> Generator[Path, None, None]:
        """
        Context manager for a temporary file containing the embedded
        docker-compose specification.

        Yields
        ------
            A temporary file containing the docker-compose spec.

        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)

            # write compose definition to a temporary file
            compose_file = tmp_dir / 'docker-compose.yml'
            with compose_file.open('w') as fp:
                yaml.safe_dump(self.compose, stream=fp)

            yield compose_file
            compose_file.unlink(missing_ok=True)

    def __str__(self) -> str:
        me = self.to_dict()
        me['compose'] = f'<docker-compose v3 specification, ' \
                        f'{len(self.compose)} services>'

        return json.dumps(me, indent=2, ensure_ascii=False)


class WorkloadResult(Enum):
    FINISHED = auto()
    """
    Every subtask in the workload services finished cleanly.
    """

    TIMEOUT = auto()
    """
    The workload timed out.
    """

    ERROR = auto()
    """
    One or more of the workload service subtasks exited with an error code.
    """
