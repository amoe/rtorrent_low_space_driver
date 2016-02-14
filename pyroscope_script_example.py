#! /usr/bin/env python-pyrocore

from pyrocore import config
from pyrocore.scripts import base
from pprint import pprint, pformat
import subprocess
import tempfile
import os

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
    fn_get_size_chunks = None
    fn_get_size_files = None
    fn_get_completed_chunks = None
    fn_get_path = None
    fn_set_priority = None
    fn_get_size_bytes = None

    def __init__(self, engine):
        self.engine = engine
        self.fn_get_size_chunks = getattr(engine._rpc.f, 'get_size_chunks')
        self.fn_get_size_files = getattr(engine._rpc.d, 'get_size_files')
        self.fn_get_completed_chunks = getattr(engine._rpc.f, 'get_completed_chunks')
        self.fn_get_path = getattr(engine._rpc.f, 'get_path')
        self.fn_set_priority = getattr(engine._rpc.f, 'set_priority')
        self.fn_get_size_bytes = getattr(engine._rpc.f, 'get_size_bytes')

    def get_size_chunks(self, id_):
        return self.fn_get_size_chunks(id_)

    def get_size_files(self, id_):
        return self.fn_get_size_files(id_)

    def get_completed_chunks(self, id_):
        return self.fn_get_completed_chunks(id_)

    def get_path(self, id_):
        return self.fn_get_path(id_)
    
    def set_priority(self, id_, priority):
        return self.fn_set_priority(id_, priority)

    def get_size_bytes(self, id_):
        return self.fn_get_size_bytes(id_)


class RtorrentLowSpaceDriver(base.ScriptBaseWithConfig):
    """rtorrent low space driver"""

    # argument description for the usage information
    ARGS_HELP = "<arg_1>... <arg_n>"

    # five gigabyte space limit
    SPACE_LIMIT = 5 * (2 ** 30);

    my_proxy = None
    infohash = None

    def add_options(self):
        super(RtorrentLowSpaceDriver, self).add_options()
        # basic options
        ##self.add_bool_option("-n", "--dry-run",
        ##    help="don't do anything, just tell what would happen")


    def mainloop(self):
        proxy = config.engine.open()
        self.my_proxy = MyProxy(config.engine)
        # store hash in external file
        self.infohash = open('hash.txt').read().rstrip()
        items = config.engine.items()
        
        this_item = None
        for i in items:
            if i.hash == self.infohash:
                this_item = i
                break
        self.LOG.info("Managing torrent: %s" % this_item.name)

        self.stop_torrent(this_item)
        local_completed_files = self.check_for_local_completed_files()

        self.LOG.info("Locally completed files: %s" % pformat(local_completed_files))

        self.sync_completed_files_to_remote(local_completed_files)
        remote_completed_list = self.scan_remote_for_completed_list()
        pprint(remote_completed_list)

        self.remove_completed_files(local_completed_files)
        self.set_all_files_to_zero_priority()
        next_group = self.generate_next_group(remote_completed_list)

        pprint(len(next_group))
        self.set_priority([x['id'] for x in next_group], 1)
        self.start_torrent(this_item)
        
        self.LOG.info("XMLRPC stats: %s" % proxy)

    def stop_torrent(self, torrent):
        torrent.stop()

    # returns list of locally completed files as IDs
    def check_for_local_completed_files(self):
        completed_list = []
        
        size_files = self.my_proxy.get_size_files(self.infohash)

        for i in range(size_files):
            id_ = "%s:f%d" % (self.infohash, i)
            done = self.my_proxy.get_completed_chunks(id_)
            total = self.my_proxy.get_size_chunks(id_)
            
            if done == total:
                completed_list.append(my_proxy.get_path(i))
                
        return completed_list

    def sync_completed_files_to_remote(self, completed_files):
        with tempfile.NamedTemporaryFile(
            suffix=".lst", prefix="transfer_list-", delete=False
        ) as transfer_list:
            for path in completed_files:
                transfer_list.write(path + "\n")

            subprocess.check_call([
                "rsync", "-aPv", "--files-from=" + transfer_list.name,
                "/home/amoe/download", "kupukupu:/tmp"
            ])
            os.remove(transfer_list.name)

            # XXX: Really need to handle errors & retry until success

    def scan_remote_for_completed_list(self):
        output = subprocess.check_output(["ssh", "kupukupu", "ls", "/tmp"])
        remote_files = output.rstrip().split("\n")
        return remote_files

    def remove_completed_files(self, completed_files):
        for path in completed_files:
            os.remove(path)

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

    def start_torrent(self, torrent):
        torrent.start()

if __name__ == "__main__":
    base.ScriptBase.setup()
    RtorrentLowSpaceDriver().run()
