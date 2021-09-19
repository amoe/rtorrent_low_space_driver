from logging import debug, info, error, warning
import time
import subprocess
import pipes
import os
from abc import ABC, abstractmethod
from pprint import pformat


def get_service(**kwargs):
    """Returns the appropriate class."""
    if ('remote_sync_service' not in kwargs
            and 'remote_host' in kwargs
            and 'remote_path' in kwargs):
        # If all three conditions are satisfied, the user is using the old template format.
        # We must convert it to the new format.
        kwargs['remote_sync_service'] = 'rsync'
        kwargs['rsync_host'] = kwargs.pop('remote_host')
        kwargs['rsync_path'] = kwargs.pop('remote_path')
    return Rsync(**kwargs)


class RemoteSyncEngine(ABC):
    """Defines remote sync interface."""
    @abstractmethod
    def __init__(self, **kwargs):
        pass

    @abstractmethod
    def get_remote_path(self, realpath):
        pass

    @abstractmethod
    def maybe_create_directory(self, realpath):
        pass

    @abstractmethod
    def sync_path(self, base_path, base_filename):
        pass

    @abstractmethod
    def list_files(self, realpath):
        pass

    @abstractmethod
    def sync_files_from_filelist(self, realpath, filelist_path):
        pass


class Rsync(RemoteSyncEngine):
    pass
