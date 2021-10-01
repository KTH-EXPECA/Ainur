import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Mapping

import yaml


def _check_dir_exists(d: Path):
    if not d.exists() or not d.is_dir():
        raise RuntimeError(
            f'{d} either does not exist or is not a directory.')


# TODO: test

class AnsibleContext:
    def __init__(self, base_dir: Path):
        super(AnsibleContext, self).__init__()

        # check structure of dir
        self._base_dir = base_dir
        _check_dir_exists(self._base_dir)

        # necessary subdirs are ./env and ./project
        self._env_dir = base_dir / 'env'
        self._proj_dir = base_dir / 'project'
        _check_dir_exists(self._env_dir)
        _check_dir_exists(self._proj_dir)

    @contextmanager
    def __call__(self, inventory: Mapping) -> Generator[Path, None, None]:
        """
        Creates a temporary environment to use in combination with
        ansible-runner.

        Example usage::

            with ansible_ctx(inventory) as tmp_dir:
                ansible_runner.run(
                    playbook='test.yml',
                    private_data_dir=str(tmp_dir)
                )


        Parameters
        ----------
        inventory
            The inventory to use in this context.

        Returns
        -------
        Path
            A Path object pointing to the temporary Ansible environment.
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)

            # set up the file structure ansible-runner expects,
            # inside the tmpdir by symlinking stuff
            os.symlink(self._proj_dir, tmp_dir / 'project')
            os.symlink(self._env_dir, tmp_dir / 'env')

            # make a temporary inventory dir and dump the dict
            inv_dir = tmp_dir / 'inventory'
            inv_dir.mkdir(parents=True, exist_ok=True)
            with (inv_dir / 'hosts').open('w') as fp:
                yaml.safe_dump(inventory, stream=fp)

            yield tmp_dir
