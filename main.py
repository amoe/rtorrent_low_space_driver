#! /usr/bin/env python

import sys
import logging
from logging import debug, info
import argparse
import libtorrent
import os

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

    def run(self, args):
        ns = self.initialize(args)
        
        info("Starting.")

        list_of_torrents = []

        for torrent in os.listdir(self.MANAGED_TORRENTS_DIRECTORY):
            full_path = os.path.join(self.MANAGED_TORRENTS_DIRECTORY, torrent)
            t_info = libtorrent.torrent_info(full_path)
            datum = {
                'hash': t_info.info_hash(),
                'size': t_info.total_size(),
                'path': torrent,
                'name': t_info.name(),
            }
            list_of_torrents.append(datum)


        new_list  =  sorted(list_of_torrents, key=lambda x: x['size'])

        for blah in new_list:
            print blah['name']

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
