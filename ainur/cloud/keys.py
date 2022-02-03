from __future__ import annotations

import abc
import os
import shutil
import tempfile
import uuid
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from loguru import logger

from .errors import RevokedKeyError


class AWSKeyPairBase(AbstractContextManager):
    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def private_key(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def key_file_path(self) -> str:
        pass

    @abc.abstractmethod
    def revoke(self) -> AWSKeyPairBase:
        pass

    def __enter__(self) -> AWSKeyPairBase:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.revoke()
        return super(AWSKeyPairBase, self).__exit__(exc_type, exc_val, exc_tb)


class AWSNullKeyPair(AWSKeyPairBase):
    @property
    def name(self) -> str:
        raise RevokedKeyError()

    @property
    def private_key(self) -> str:
        raise RevokedKeyError()

    @property
    def key_file_path(self) -> str:
        raise RevokedKeyError()

    def revoke(self) -> AWSKeyPairBase:
        return self


class AWSKeyPair(AWSKeyPairBase):
    def __init__(self, region: str, name: Optional[str] = None):
        # request new keypair from AWS
        ec2 = boto3.resource('ec2', region_name=region)
        key_name = name if name is not None else f'key-{uuid.uuid4().hex}'

        logger.info(f'Creating ephemeral key pair {key_name} for instance '
                    f'access on region {region}.')

        self._key = ec2.create_key_pair(KeyName=key_name)
        self._region = region

        self._key_dir = Path(tempfile.mkdtemp(prefix='ainur_')).resolve()
        self._key_file = (self._key_dir / f'{uuid.uuid4().hex}').resolve()

        # store key to file
        with self._key_file.open('w') as fp:
            fp.write(self._key.key_material)

        os.chmod(self._key_file, 0o600)

        logger.debug(f'Key {key_name} has been created and stored on-disk '
                     f'at {self._key_file}.')

        self._revoked = False

    def _check(self) -> None:
        if self._revoked:
            raise RevokedKeyError()

    @property
    def name(self) -> str:
        self._check()
        return self._key.key_name

    @property
    def private_key(self) -> str:
        self._check()
        return self._key.key_material

    @property
    def key_file_path(self) -> str:
        self._check()
        return str(self._key_file)

    def revoke(self) -> AWSKeyPairBase:
        if self._revoked:
            return AWSNullKeyPair()

        logger.warning(f'Revoking AWS key {self.name}...')
        shutil.rmtree(self._key_dir)

        # delete the key from ec2
        try:
            ec2 = boto3.resource('ec2', region_name=self._region)
            key = ec2.KeyPair(self._key.name)
            key.load()
            logger.debug(f'Deleting ephemeral key {key.key_name} on AWS...')
            key.delete()
        except ClientError:
            pass

        self._revoked = True
        logger.debug('Key revoked.')
        return AWSNullKeyPair()
