#! /usr/bin/env python-pyrocore

from pyrocore import config
from pyrocore.scripts import base
from pprint import pprint, pformat
import subprocess

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

    def __init__(self, engine):
        self.engine = engine
        self.fn_get_size_chunks = getattr(engine._rpc.f, 'get_size_chunks')

    def get_size_chunks(self, id_):
        return self.fn_get_size_chunks(id_)
        

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
        self.sync_completed_files_to_remote()
        remote_completed_list = self.scan_remote_for_completed_list()
        pprint(remote_completed_list)

        self.remove_completed_files()
        self.set_all_files_to_zero_priority()
        next_group = self.generate_next_group(remote_completed_list)
        self.set_priority(next_group, 1)
        self.start_torrent(this_item)
        
        self.LOG.info("XMLRPC stats: %s" % proxy)

    def stop_torrent(self, torrent):
        torrent.stop()

    def check_for_local_completed_files(self):
        result = self.my_proxy.get_size_chunks(self.infohash + ":f1")
        pprint(result)

    def sync_completed_files_to_remote(self):
        pass

    def scan_remote_for_completed_list(self):
        output = subprocess.check_output(["ssh", "kupukupu", "ls", "/tmp"])
        remote_files = output.rstrip().split("\n")
        return remote_files

    def remove_completed_files(self):
        pass

    def set_all_files_to_zero_priority(self):
        pass

    def generate_next_group(self, exclude_list):
        pass

    def set_priority(self, ids, priority):
        pass

    def start_torrent(self, torrent):
        torrent.start()

if __name__ == "__main__":
    base.ScriptBase.setup()
    RtorrentLowSpaceDriver().run()


