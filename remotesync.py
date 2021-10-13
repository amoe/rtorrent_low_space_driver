from logging import debug, info, error, warning
import time
import subprocess
import pipes
import os
from abc import ABC, abstractmethod
from pprint import pformat


def get_service(**kwargs):
    """Returns the appropriate class that implements RemoteSyncEngine interface."""
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
    """Abstract Class: Remote sync interface."""
    @abstractmethod
    def __init__(self, **kwargs):
        pass

    @abstractmethod
    def get_remote_path(self, realpath):
        """Returns path in the remote."""
        pass

    @abstractmethod
    def maybe_create_directory(self, realpath):
        """Create a directory in the remote."""
        pass

    @abstractmethod
    def sync_path(self, base_path, base_filename):
        """Copy the object of path to remote."""
        pass

    @abstractmethod
    def list_files(self, realpath):
        """List files in the remote."""
        pass

    @abstractmethod
    def sync_files_from_filelist(self, realpath, filelist_path):
        """Copy files from filelist to remote."""
        pass


class Rsync(RemoteSyncEngine):
    """Implements the interface for usage with Rsync"""
    # We provide a timeout so that the receive-side rsync --server process
    # can exit properly before we try to reconnect to the receiving host.
    # The idea comes from <https://stackoverflow.com/questions/16572066/>
    #
    # Use a very conservative wait time so that we account for any disparity
    # between the timeouts activating on the server and client side.
    RECEIVE_SERVER_TIMEOUT = 15
    LOCAL_WAIT_TIME = RECEIVE_SERVER_TIMEOUT * 10

    def __init__(self, **kwargs):
        self.RSYNC_HOST = kwargs.get('rsync_host')
        self.RSYNC_PATH = kwargs.get('rsync_path')

    def get_remote_path(self, realpath):
        return os.path.join(self.RSYNC_PATH, os.path.basename(realpath))

    def maybe_create_directory(self, realpath):
        remote_path = self.get_remote_path(realpath)

        while True:
            try:
                # remote path must be quoted, lest it be interpreted wrongly
                # by the shell on the server side.
                subprocess.check_call([
                    "ssh", self.RSYNC_HOST, "mkdir", "-p",
                    pipes.quote(remote_path)
                ])

                return
            except subprocess.CalledProcessError as e:
                error("failed to read remote, retrying.  exception was '%s'" % e)
                time.sleep(60)

    def sync_path(self, base_path, base_filename):
        cmd = self.rsync_command() + [
            base_path, self.RSYNC_HOST + ":" + self.RSYNC_PATH
        ]

        while True:
            try:
                info("running command: %s" % pformat(cmd))
                subprocess.check_call(cmd)
                return
            except subprocess.CalledProcessError as e:
                # This can happen in some strange cases such as when multiple
                # managed torrents exist that use the same source directory and
                # finish at the same time.  One previously synced torrent can
                # cause the source path to be purged, which will also
                # accidentally purge files from another torrent.  We don't
                # really care about this edge case at present.
                if not os.path.exists(base_path):
                    error(
                        "Somehow the source path no longer existed.  This should never happen, bailing out of this "
                        "transfer.")
                    break

                error("failed to sync files to remote, retrying.  exception was '%s'" % e)
                self.pessimistic_wait()

    def list_files(self, realpath):
        remote_path = self.get_remote_path(realpath)

        while True:
            try:
                # remote path must be quoted, lest it be interpreted wrongly
                # by the shell on the server side.
                output = subprocess.check_output([
                    "ssh", self.RSYNC_HOST, "find", pipes.quote(remote_path),
                    "-type", "f", "-print"
                ])

                # Decode all output immediately and split it, remember that
                # rtorrent is returning unicode strings to us so we need
                # to create unicode strings so that they can be compared
                # to the list of locally completed files.
                remote_files = output.decode('UTF-8').rstrip().split("\n")

                return [
                    x[len(remote_path + "/"):] for x in remote_files
                    if x.startswith(self.RSYNC_PATH)
                ]
            except subprocess.CalledProcessError as e:
                error("failed to read remote, retrying.  exception was '%s'" % e)
                time.sleep(60)

    def sync_files_from_filelist(self, realpath, filelist_path):
        remote_path = "%s:%s" \
                      % (self.RSYNC_HOST, pipes.quote(self.get_remote_path(realpath)))

        # slash on the end of the local path makes sure that we sync to remote
        # path, rather than creating a subdir
        cmd = self.rsync_command() + [
            "--files-from=" + filelist_path, realpath + "/", remote_path
        ]

        while True:
            try:
                info("running command: %s", ' '.join(cmd))
                subprocess.check_call(cmd)
                return
            except subprocess.CalledProcessError as e:
                error("failed to sync files to remote, retrying.  exception was '%s'" % e)
                self.pessimistic_wait()

    def rsync_command(self):
        rst = self.RECEIVE_SERVER_TIMEOUT
        return [
            'rsync', '-aPv', f"--timeout={rst}"
        ]

    def pessimistic_wait(self):
        time.sleep(self.LOCAL_WAIT_TIME)
