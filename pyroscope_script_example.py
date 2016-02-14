#! /usr/bin/env python-pyrocore

from pyrocore import config
from pyrocore.scripts import base
from pprint import pprint, pformat

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



class RtorrentLowSpaceDriver(base.ScriptBaseWithConfig):
    """rtorrent low space driver"""

    # argument description for the usage information
    ARGS_HELP = "<arg_1>... <arg_n>"

    # five gigabyte space limit
    SPACE_LIMIT = 5 * (2 ** 30);

    def add_options(self):
        super(RtorrentLowSpaceDriver, self).add_options()
        # basic options
        ##self.add_bool_option("-n", "--dry-run",
        ##    help="don't do anything, just tell what would happen")


    def mainloop(self):
        proxy = config.engine.open()
        # store hash in external file
        infohash = open('hash.txt').read().rstrip()
        
        self.stop_torrent()
        self.check_for_completed_files()
        self.sync_completed_files_to_remote()
        completed_list = self.scan_remote_for_completed_list()
        self.remove_completed_files()
        self.set_all_files_to_zero_priority()
        next_group = self.generate_next_group(completed_list)
        self.set_priority(next_group, 1)
        self.start_torrent()
        
        self.LOG.info("XMLRPC stats: %s" % proxy)

    def stop_torrent(self):
        pass

    def check_for_completed_files(self):
        pass

    def sync_completed_files_to_remote(self):
        pass

    def scan_remote_for_completed_list(self):
        pass

    def remove_completed_files(self):
        pass

    def set_all_files_to_zero_priority(self):
        pass

    def generate_next_group(self, exclude_list):
        pass

    def set_priority(self, ids, priority):
        pass

    def start_torrent(self):
        pass

if __name__ == "__main__":
    base.ScriptBase.setup()
    RtorrentLowSpaceDriver().run()


