import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Mapping, Optional, Union

import yaml
from loguru import logger


def _check_dir_exists(d: Path):
    if not d.exists() or not d.is_dir():
        raise RuntimeError(
            f'{d} either does not exist or is not a directory.')


# TODO: test

class AnsibleContext:
    """
    Utility class for easy execution of ansible-runner in temporary contexts.
    Ansible-runner tends to generate and cache a lot of "junk", and this
    class implements a way of avoiding that.

    Usage example::

        ansible_ctx = AnsibleContext(...)
        ...
        with ansible_ctx(inventory) as tmp_dir:
                ansible_runner.run(
                    playbook='test.yml',
                    private_data_dir=str(tmp_dir)
                )
    """

    def __init__(self, base_dir: Path):
        """
        Parameters
        ----------
        base_dir
            Base directory for the Ansible runner configuration. Should have
            env and project subdirectories.
        """

        super(AnsibleContext, self).__init__()

        # check structure of dir
        # we need full path
        self._base_dir = base_dir.resolve()
        _check_dir_exists(self._base_dir)

        # necessary subdirs are ./env and ./project
        self._env_dir = (base_dir / 'env').resolve()
        self._proj_dir = (base_dir / 'project').resolve()
        _check_dir_exists(self._env_dir)
        _check_dir_exists(self._proj_dir)

        logger.debug(f'Initialized Ansible context at {self._base_dir}')

    @contextmanager
    def __call__(self,
                 inventory: Mapping,
                 ssh_key: Optional[Union[os.PathLike, str]] = None,
                 **extravars: Any) \
            -> Generator[Path, None, None]:
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
        ssh_key
            Specify the SSH key file to use for this context.
        extravars
            Extravar overrides.

        Returns
        -------
        Path
            A Path object pointing to the temporary Ansible environment.
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)

            # set up the file structure ansible-runner expects,
            # inside the tmpdir
            os.symlink(self._proj_dir, tmp_dir / 'project')
            # os.symlink(self._env_dir, tmp_dir / 'env')
            shutil.copytree(self._env_dir, tmp_dir / 'env')

            # potentially override some extravars
            extravars_file = ((tmp_dir / 'env') / 'extravars')
            try:
                with extravars_file.open('r') as fp:
                    orig_extravars = yaml.safe_load(fp)
                if orig_extravars is None:
                    orig_extravars = {}
                elif not isinstance(orig_extravars, Dict):
                    raise RuntimeError('Ansible extravars file should be an '
                                       'YAML file containing a mapping!')
            except FileNotFoundError:
                orig_extravars = {}

            orig_extravars.update(extravars)
            with extravars_file.open('w') as fp:
                yaml.safe_dump(orig_extravars, stream=fp)

            # if using a custom ssh key, copy it to the env dir
            if ssh_key is not None:
                ssh_key = Path(ssh_key).resolve()
                ssh_key_path = tmp_dir / 'env' / 'ssh_key'
                shutil.copy(ssh_key, ssh_key_path)
                os.chmod(ssh_key_path, 0o600)

            # make a temporary inventory dir and dump the dict
            inv_dir = tmp_dir / 'inventory'
            inv_dir.mkdir(parents=True, exist_ok=True)
            with (inv_dir / 'hosts').open('w') as fp:
                yaml.safe_dump(inventory, stream=fp)

            logger.debug(f'Created temporary Ansible '
                         f'execution context at {tmp_dir}')
            try:
                yield tmp_dir
            finally:
                logger.debug(f'Tearing down temporary Ansible '
                             f'execution context at {tmp_dir}')
