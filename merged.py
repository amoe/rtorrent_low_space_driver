#! /usr/bin/env python

import sys
import logging
from logging import debug, info
import argparse
import os
import rtorrent_xmlrpc
import pprint

def splitter(data, pred):
    yes, no = [], []
    for d in data:
        if pred(d):
            yes.append(d)
        else:
            no.append(d)
    return [yes, no]

class RtorrentLowSpaceDriver(object):
    MANAGED_TORRENTS_DIRECTORY = "/home/amoe/dev/rtorrent_low_space_driver/managed"
    REMOTE_HOST = "kupukupu"
    REMOTE_PATH = "/mnt/spock/mirror2"
    SPACE_LIMIT = 3 * (2 ** 30)
    REQUIRED_RATIO = 1.0

    server = None
    
    def run(self, args):
        ns = self.initialize(args)

        info("Starting.")

        self.server = rtorrent_xmlrpc.SCGIServerProxy(
            "scgi:///home/amoe/.rtorrent.sock"
        )

        self.handle_small_torrents_strategy()
        self.handle_large_torrent_strategy()
        info("Done.")

    ## SMALL TORRENT STRATEGY

    def handle_small_torrents_strategy(self):
        managed_torrents = self.build_managed_torrents_list()
        rt_complete, rt_incomplete = self.get_torrents_from_rtorrent()
        self.sync_and_remove(
            [managed_torrents[t] for t in rt_complete
             if t in managed_torrents]
        )
        effective_space = self.compute_effective_available_space(
            [managed_torrents[t] for t in rt_incomplete
             if t in managed_torrents]
        )
        info("Available size to load is %d", effective_space)

        load_candidates = self.filter_out_managed_items_already_in_client(
            managed_torrents, rt_incomplete, rt_complete
        )
        load_choices = self.build_next_load_group(
            load_candidates, effective_space
        )

        info("Decided to load these torrents: %s" % pprint.pformat(load_choices))
        self.load_torrents(load_choices)

    # make lookup table for torrents, should be a set
    def build_managed_torrents_list(self):
        managed_torrents = {}
        for torrent in os.listdir(self.MANAGED_TORRENTS_DIRECTORY):
             full_path = os.path.join(self.MANAGED_TORRENTS_DIRECTORY, torrent)
             t_info = libtorrent.torrent_info(full_path)
             hash_ = str(t_info.info_hash()).upper()
             # We redundantly store the hash in the value, just to make things
             # easier a bit later
             datum = {
                 'torrent_path': full_path,
                 'size': t_info.total_size(),
                 'name': t_info.name(),
                 'hash': hash_,
             }
             managed_torrents[hash_] = datum
        return managed_torrents

    def get_torrents_from_rtorrent(self):
        return splitter(
            self.server.download_list(), lambda t: self.server.d.complete(t) == 1
        )

    def sync_and_remove(self, torrent_list):
        for completed_torrent in torrent_list:
            infohash_ = completed_torrent['hash']
            info("Handling completed torrent: %s" % completed_torrent['name'])

            ratio = server.d.get_ratio(infohash)
            if ratio < self.REQUIRED_RATIO:
                info("Torrent is completed but not seeded to required ratio.  Skipping.")
                continue

            base_path = server.d.get_base_path(infohash)
            self.sync_completed_path_to_remote(base_path)
            server.d.erase(infohash)

            if os.path.isdir(base_path):
                shutil.rmtree(base_path)
            else:
                os.remove(base_path)

            torrent_path = completed_torrent['torrent_path']
            if os.path.exists(torrent_path):
                info("For some reason tied torrent existed.  Killing it.")
                os.remove(torrent_path)
            else:
                info("Tied torrent file was already deleted by rtorrent.")
    
    def compute_effective_available_space(self, torrent_list):
        # Count incomplete torrents
        cumulative_incomplete_size = 0
        for incomplete_torrent in torrent_list:
            cumulative_incomplete_size += managed_torrent['size']

        info("Cumulative size of incomplete items was %d" % cumulative_incomplete_size)
        effective_available_size = self.SPACE_LIMIT - cumulative_incomplete_size

        return effective_available_size

    def filter_out_managed_items_already_in_client(
        self, managed_group, incomplete_group, complete_group
    ):
        # Filter out the managed items that were already loaded
        not_already_loaded = []
        for k, v in managed_group.iteritems():
            if k not in rt_incomplete and k not in rt_complete:
                not_already_loaded.append(v)

        return not_already_loaded

    def build_next_load_group(self, candidates, space):
        # Pick the first set that will fit
        by_size = sorted(candidates, key=lambda t: t['size'])
        this_group = []
        total_size = 0

        for torrent in by_size:
            if (total_size + torrent['size']) > space:
                break
            this_group.append(torrent)
            total_size += torrent['size']

        return this_group

    def load_torrents(self, torrent_paths):
        for torrent_to_load in torrent_paths:
            server.load_start(torrent_to_load['torrent_path'])


    ## LARGE TORRENT STRATEGY

    # The large torrent strategy always works on a single torrent at a time.
    # This has to already have been loaded.
    def handle_large_torrent_strategy(self, infohash):
        realpath = self.my_proxy.get_directory(infohash)

        info("Managing torrent: %s" % realpath)

        self.stop_torrent(infohash)
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
        self.start_torrent(infohash)
        
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
