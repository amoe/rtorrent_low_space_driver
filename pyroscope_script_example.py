#! /usr/bin/env python-pyrocore

# Enter the magic kingdom
from pyrocore import config
from pyrocore.scripts import base
from pprint import pprint, pformat

import pdb

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

        self.LOG.info("XMLRPC stats: %s" % proxy)



if __name__ == "__main__":
    base.ScriptBase.setup()
    RtorrentLowSpaceDriver().run()


