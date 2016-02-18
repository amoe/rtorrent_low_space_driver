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
    MANAGED_TORRENTS_DIRECTORY = "/home/amoe/download/torrents"
    REMOTE_HOST = "kupukupu"
    REMOTE_PATH = "/mnt/spock/mirror2"
    SPACE_LIMIT = 3 * (2 ** 30)

    def run(self, args):
        ns = self.initialize(args)
        
        info("Starting.")

        # make lookup table for torrents, should be a set
        managed_torrents = {}
        for torrent in os.listdir(self.MANAGED_TORRENTS_DIRECTORY):
             full_path = os.path.join(self.MANAGED_TORRENTS_DIRECTORY, torrent)
             t_info = libtorrent.torrent_info(full_path)
             hash_ = str(t_info.info_hash()).upper()
             datum = {'torrent_path': full_path}
             managed_torrents[hash_] = datum


        # Check for completed downloads
        server = rtorrent_xmlrpc.SCGIServerProxy("scgi:///home/amoe/.rtorrent.sock")

        rtorrent_completed_list = [
            t.upper() for t in server.download_list()
            if server.d.complete(t) == 1
        ]


        for completed_torrent in rtorrent_completed_list:
            # print "directory = ", server.d.get_directory(completed_torrent)
            # print "directory base = ", server.d.get_directory_base(completed_torrent)
            # print "loaded file = ", server.d.get_loaded_file(completed_torrent)
            # print "base filename = ", server.d.get_base_filename(completed_torrent)
            managed_torrent = managed_torrents.get(completed_torrent)
            if managed_torrent:
                base_path = server.d.get_base_path(completed_torrent)
                self.sync_completed_path_to_remote(base_path)
                server.d.erase(completed_torrent)
                os.path.remove(managed_torrent['torrent_path'])

            # now we know it's done.  so remove it from the list.

            #print os.path.dirname(server.d.get_loaded_file(completed_torrent))
            

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


        # list_of_torrents = []

        # for torrent in os.listdir(self.MANAGED_TORRENTS_DIRECTORY):
        #     full_path = os.path.join(self.MANAGED_TORRENTS_DIRECTORY, torrent)
        #     t_info = libtorrent.torrent_info(full_path)
        #     hash_ = t_info.info_hash()

        #     datum = {
        #         'hash': t_info.info_hash(),
        #         'size': t_info.total_size(),
        #         'path': torrent,
        #         'name': t_info.name(),
        #     }
        #     list_of_torrents.append(datum)


        # new_list  =  sorted(list_of_torrents, key=lambda x: x['size'])

        # this_list = []
        # total_size = 0

        # for torrent in new_list:
        #     if (total_size + torrent['size']) > self.SPACE_LIMIT:
        #         break
        #     this_list.append(torrent)
        #     total_size += torrent['size']

        # pprint.pprint(this_list)
        # print self.SPACE_LIMIT
        # print total_size

        info("End.")
        
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
