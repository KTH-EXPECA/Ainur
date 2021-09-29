import os
import tempfile
from collections import Collection, Generator
from contextlib import contextmanager
from pathlib import Path

import yaml


@contextmanager
def ansible_temp_dir(
        inventory: dict,
        playbooks: Collection[str] = (),
        base_playbook_dir: Path = Path('../playbooks')
) -> Generator[Path, None, None]:
    # TODO: maybe make an object?

    # ansible-runner is stupid and expects everything to be an *actual* file
    # we will trick it by using temporary directories and files
    # on Linux this should all happen in a tmpfs, so no disk writes necessary
    # this also helps avoid the clutter that ansible-runner otherwise generates
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)

        # set up the file structure ansible-runner expects, inside the tmpdir
        proj_dir = tmp_dir / 'project'
        proj_dir.mkdir(parents=True)

        inv_dir = tmp_dir / 'inventory'
        inv_dir.mkdir(parents=True)

        # link the playbooks to the temp dir
        # shutil.copy(playbook_dir / 'swarm_up.yml', proj_dir)
        for pbook in playbooks:
            os.symlink(base_playbook_dir.resolve() / pbook,
                       proj_dir / pbook)

        # dump the inventory
        with (inv_dir / 'hosts').open('w') as fp:
            yaml.safe_dump(inventory, stream=fp)

        yield tmp_dir
