#! /usr/bin/env python

import sys
import logging
from logging import debug, info
import argparse
import libtorrent
import os
import pprint
import rtorrent_xmlrpc
import tempfile
import subprocess
import shutil

def splitter(data, pred):
    yes, no = [], []
    for d in data:
        if pred(d):
            yes.append(d)
        else:
            no.append(d)
    return [yes, no]

# Algorithm for this.

# Can it run from cron.
# Needs to find the size of each torrent in the torrent dir,
# which must be separate from rtorrent's watched dir.
# Sort the list by size, smallest first.
# Now add the torrents to the watched dir.
# We guarantee that -- EITHER multiple torrents are present.  If multiple torrents are present, then the total can fit inside the space limit.
# OR a single torrent is present, in which case it may not fit inside the space limit.
# Can the total fit on the disk?

class RtorrentLowSpaceDriver(object):
    MANAGED_TORRENTS_DIRECTORY = "/home/amoe/dev/rtorrent_low_space_driver/managed"
    REMOTE_HOST = "kupukupu"
    REMOTE_PATH = "/mnt/spock/mirror2"
    SPACE_LIMIT = 3 * (2 ** 30)
    REQUIRED_RATIO = 1.0

    def run(self, args):
        ns = self.initialize(args)
        
        info("Starting.")

        # make lookup table for torrents, should be a set
        managed_torrents = {}
        for torrent in os.listdir(self.MANAGED_TORRENTS_DIRECTORY):
             full_path = os.path.join(self.MANAGED_TORRENTS_DIRECTORY, torrent)
             t_info = libtorrent.torrent_info(full_path)
             hash_ = str(t_info.info_hash()).upper()
             datum = {
                 'torrent_path': full_path,
                 'size': t_info.total_size(),
                 'name': t_info.name()
             }
             managed_torrents[hash_] = datum


        # Check for completed downloads
        server = rtorrent_xmlrpc.SCGIServerProxy(
            "scgi:///home/amoe/.rtorrent.sock"
        )


        rt_complete, rt_incomplete = splitter(
            server.download_list(), lambda t: server.d.complete(t) == 1
        )

        # Sync & remove complete torrents
        for completed_torrent in rt_complete:
            managed_torrent = managed_torrents.get(completed_torrent)
            if managed_torrent:
                info("Handling completed torrent: %s" % managed_torrent['name'])

                ratio = server.d.get_ratio(completed_torrent)
                if ratio < self.REQUIRED_RATIO:
                    info("Torrent is completed but not seeded to required ratio.  Skipping.")
                    continue

                base_path = server.d.get_base_path(completed_torrent)
                self.sync_completed_path_to_remote(base_path)
                server.d.erase(completed_torrent)
                
                if os.path.isdir(base_path):
                    shutil.rmtree(base_path)
                else:
                    os.remove(base_path)

                torrent_path = managed_torrent['torrent_path']
                if os.path.exists(torrent_path):
                    info("For some reason tied torrent existed.  Killing it.")
                    os.remove(torrent_path)
                else:
                    info("Tied torrent file was already deleted by rtorrent.")

        # Count incomplete torrents
        cumulative_incomplete_size = 0
        for incomplete_torrent in rt_incomplete:
            managed_torrent = managed_torrents.get(incomplete_torrent)
            if managed_torrent:
                cumulative_incomplete_size += managed_torrent['size']

        info("Cumulative size of incomplete items was %d" % cumulative_incomplete_size)
        effective_available_size = self.SPACE_LIMIT - cumulative_incomplete_size
        info("Available size to load is %d", effective_available_size)

        # Filter out the managed items that were already loaded
        not_already_loaded = []
        for k, v in managed_torrents.iteritems():
            if k not in rt_incomplete and k not in rt_complete:
                not_already_loaded.append(v)

        # Pick the first set that will fit
        managed_by_size = sorted(not_already_loaded, key=lambda t: t['size'])
        this_list = []
        total_size = 0

        for torrent in managed_by_size:
            if (total_size + torrent['size']) > effective_available_size:
                break
            this_list.append(torrent)
            total_size += torrent['size']

        info("Decided to load these torrents: %s" % pprint.pformat(this_list))

        for torrent_to_load in this_list:
            server.load_start(torrent_to_load['torrent_path'])

        info("End.")

    def sync_completed_path_to_remote(self, source_path):
        cmd = [
            "rsync", "-aPv", source_path, 
            self.REMOTE_HOST + ":" + self.REMOTE_PATH
        ]

        while True:
            try:
                info("running command: %s", ' '.join(cmd))
                subprocess.check_call(cmd)
                return
            except subprocess.CalledProcessError, e:
                error("failed to sync files to remote, retrying.  exception was '%s'" % e)
                time.sleep(60)

        
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

        

if __name__ == "__main__":
    obj = RtorrentLowSpaceDriver()
    obj.run(sys.argv[1:])
