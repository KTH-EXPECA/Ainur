import contextlib
import string
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator

import yaml
from dataclasses_json import config, dataclass_json


@dataclass_json
@dataclass(frozen=True, eq=True)
class WorkloadDefinition:
    compose_v3: Dict[str, Any]
    name: str = field(
        metadata=config(
            # strip any whitespace from the name on load
            decoder=lambda s:
            s.translate(str.maketrans('', '', string.whitespace))
        )
    )
    author: str = ''
    version: str = '1.0'
    url: str = ''
    max_duration: str = '1d'

    @contextlib.contextmanager
    def temp_compose_file(self) -> Generator[Path, None, None]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)

            # write compose definition to a temporary file
            compose_file = tmp_dir / 'docker-compose.yml'
            with compose_file.open('w') as fp:
                yaml.safe_dump(self.compose_v3, stream=fp)

            yield compose_file
            compose_file.unlink(missing_ok=True)
