#! /usr/bin/env python-pyrocore

from pprint import pprint, pformat
import subprocess
import tempfile
import os
import time
import rtorrent_xmlrpc
import sys
from logging import info, debug, error
import logging
import argparse

# This will need to run as a cron.  It can run every hour perhaps.
# Each run, it stops the torrent.
# Checks for completed files.
# Syncs the completed files to the remote server, a blocking sync with retry.
# Now scans the remote path for completed files list.  Any file listed here is
# complete, because we sync single files at a time and wait until success.
# Removes the completed paths at file system level.
# Now sets all file priorities to zero.
# Now generates the next group, from every file that is NOT in the completed list.
# Now sets priorities on the next group to 1.
# Now starts the torrent.
# If there are no completed files in one run, the sync will sync zero files, and the next group will be the same as the previous group, so the operation will be idempotent.
# When the next group is zero items, the completed list will be full, the torrent will have zero space usage and all priorities will be zero.


class MyProxy(object):
    engine = None

    def __init__(self, engine):
        self.engine = engine

    def get_size_chunks(self, id_):
        return self.engine.f.get_size_chunks(id_)

    def get_size_files(self, id_):
        return self.engine.d.get_size_files(id_)

    def get_completed_chunks(self, id_):
        return self.engine.f.get_completed_chunks(id_)

    def get_path(self, id_):
        return self.engine.f.get_path(id_)
    
    def set_priority(self, id_, priority):
        return self.engine.f.set_priority(id_, priority)

    def get_size_bytes(self, id_):
        return self.engine.f.get_size_bytes(id_)

    def get_priority(self, id_):
        return self.engine.f.get_priority(id_)
    
    def update_priorities(self, id_):
        return self.engine.d.update_priorities(id_)
    
    def stop(self, id_):
        return self.engine.d.stop(id_)

    def start(self, id_):
        return self.engine.d.start(id_)

    def get_directory(self, id_):
        return self.engine.d.get_directory(id_)

    def is_active(self, id_):
        return self.engine.d.is_active(id_)


class RtorrentLowSpaceDriver(object):
    """rtorrent low space driver"""

    # argument description for the usage information
    ARGS_HELP = "<arg_1>... <arg_n>"

    # five gigabyte space limit
    SPACE_LIMIT = 2 * (2 ** 30);

    my_proxy = None
    infohash = None
    realpath = None
    remote_host = 'kupukupu'
    remote_dir = "/tmp/mirror/"   # MUST END IN SLASH

    def initialize(self, args):
        parser = argparse.ArgumentParser()

        parser.add_argument(
            '--log-level', metavar="LEVEL", type=str, help="Log level",
            default='INFO'
        )
        parser.add_argument('rest_args', metavar="ARGS", nargs='*')            
        ns = parser.parse_args(args)

        logging.basicConfig(
            level=getattr(logging, ns.log_level),            
            format="%(asctime)s - %(levelname)8s - %(name)s - %(message)s"
        )

        return ns

    def run(self, args):
        ns = self.initialize(args)
        print ns.rest_args

        server = rtorrent_xmlrpc.SCGIServerProxy("scgi:///home/amoe/.rtorrent.sock")
        self.my_proxy = MyProxy(server)

        # store hash in external file
        self.infohash = open('hash.txt').read().rstrip()
        self.realpath = self.my_proxy.get_directory(self.infohash)

        info("Managing torrent: %s" % self.realpath)

        self.stop_torrent(self.infohash)
        local_completed_files = self.check_for_local_completed_files()

        info("Locally completed files: %s" % pformat(local_completed_files))

        self.sync_completed_files_to_remote(local_completed_files)
        remote_completed_list = self.scan_remote_for_completed_list()

        info("Remotely completed files: %s" % pformat(remote_completed_list))

        self.remove_completed_files(local_completed_files)
        self.set_all_files_to_zero_priority()
        next_group = self.generate_next_group(remote_completed_list)

        self.set_priority([x['id'] for x in next_group], 1)

        # NB: hash check?
        self.start_torrent(self.infohash)

    def stop_torrent(self, infohash):
        self.my_proxy.stop(infohash)


    def sync_completed_files_to_remote(self, completed_files):
        tmpfile_path = None
        
        with tempfile.NamedTemporaryFile(
            suffix=".lst", prefix="transfer_list-", delete=False
        ) as transfer_list:
            tmpfile_path = transfer_list.name

            for path in completed_files:
                transfer_list.write(path + "\n")
        
        cmd = [
            "rsync", "-aPv", "--files-from=" + tmpfile_path,
            self.realpath, self.remote_host + ":" + self.remote_dir
        ]

        while True:
            try:
                info("running command: %s", ' '.join(cmd))
                subprocess.check_call(cmd)
                os.remove(transfer_list.name)
                return
            except subprocess.CalledProcessError, e:
                error("failed to sync files to remote, retrying.  exception was '%s'" % e)
                time.sleep(60)


    def scan_remote_for_completed_list(self):
        while True:
            try:
                output = subprocess.check_output([
                    "ssh", self.remote_host, "find", self.remote_dir, "-type", "f", "-print"
                ])
                remote_files = output.rstrip().split("\n")

                return [
                    x[len(self.remote_dir):] for x in remote_files
                    if x.startswith(self.remote_dir)
                ]
            except subprocess.CalledProcessError, e:
                error("failed to read remote, retrying.  exception was '%s'" % e)
                time.sleep(60)

    def remove_completed_files(self, completed_files):
        for path in completed_files:
            self._zero_out_file(os.path.join(self.realpath, path))
        subprocess.check_call(["sync"])

    def set_all_files_to_zero_priority(self):
        id_list = []
        file_len = self.my_proxy.get_size_files(self.infohash)
        
        for i in range(file_len):
            id_list.append("%s:f%d" % (self.infohash, i))

        self.set_priority(id_list, 0)

    def generate_next_group(self, exclude_list):
        file_len = self.my_proxy.get_size_files(self.infohash)
        file_list = []
        for i in range(file_len):
            id_ = "%s:f%d" % (self.infohash, i)
            size = self.my_proxy.get_size_bytes(id_)
            path = self.my_proxy.get_path(id_)
            datum = {
                'id': id_, 'size': size, 'path': path
            }
            file_list.append(datum)

        # filter out items existing on remote
        filtered_items = [x for x in file_list if x['path'] not in exclude_list]

        # sort items by size
        filtered_items.sort(key=lambda x: x['size'])

        # pick until we hit the space limit
        size_so_far = 0
        group = []
        for file_ in filtered_items:
            this_size = file_['size']
            if (size_so_far + this_size) > self.SPACE_LIMIT:
                break
            
            size_so_far += this_size
            group.append(file_)

        return group
        

    def set_priority(self, ids, priority):
        for id_ in ids:
            self.my_proxy.set_priority(id_, priority)
        self.my_proxy.update_priorities(self.infohash)

    def start_torrent(self, infohash):
        while True:
            self.my_proxy.start(infohash)
            time.sleep(1)
            if self.my_proxy.is_active(infohash) == 1:
                break
            else:
                error("failed to resume torrent, retrying")
                self.my_proxy.stop(infohash)
                time.sleep(1)

    def _zero_out_file(self, path):
        open(path, 'w').close()

if __name__ == "__main__":
    RtorrentLowSpaceDriver().run(sys.argv[1:])
