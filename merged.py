#! /usr/bin/env python

import sys
import logging
from logging import debug, info
import argparse
import os
import rtorrent_xmlrpc
import pprint
import libtorrent
import subprocess

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
    REMOTE_HOST = "localhost"
    REMOTE_PATH = "/home/amoe/mymirror"
    SPACE_LIMIT = 3 * (2 ** 30)
    REQUIRED_RATIO = 0.0

    server = None
    
    def run(self, args):
        ns = self.initialize(args)

        info("Starting.")

        self.server = rtorrent_xmlrpc.SCGIServerProxy(
            "scgi:///home/amoe/.rtorrent.sock"
        )


        large_torrent = self.check_for_large_managed_torrents()

        if large_torrent is not None:
            info("Detected incomplete & already loaded large torrent.  Switching to large strategy.")
            info("Torrent is %s" + pprint.pformat(large_torrent))
            self.handle_large_torrent_strategy(large_torrent_infohash)
        else:
            info("Using small torrents strategy per default.")
            load_candidates, load_choices = self.handle_small_torrents_strategy()
            info("Small torrents strategy finished.")
            if not load_choices:
                if load_candidates:
                    info("Large torrents blocked by small strategy.  Switching to large strategy.")
                    large_torrent = sorted(load_candidates, lambda t: t['size'])
                    self.load_torrents(large_torrent[0])
                    self.handle_large_torrent_strategy()
                else:
                    info("No candidates to load.  Either all torrents are already loaded, or there are no torrents in the managed directory.")
                    info("For you to verify, said managed torrent list is %s" % pprint.pformat(self.build_managed_torrents_list()))
                    info("Now quietly exiting successfully.")
            else:
                info("Small strategy succeeded.  See you next time!")

        info("Done.")

    ## SMALL TORRENT STRATEGY

    def check_for_large_managed_torrents(self):
        # XXX: we build this list twice
        managed_torrents = self.build_managed_torrents_list()
        rt_complete, rt_incomplete = self.get_torrents_from_rtorrent()
        
        # XXX: is rt_incomplete correct here?
        managed_torrents_in_client = [
            managed_torrents[t] for t in rt_incomplete
        ]
        
        large_managed_torrents = [
            t for t in managed_torrents_in_client
            if t['size'] > self.SPACE_LIMIT
        ]

        if large_managed_torrents:
            if len(managed_torrents_in_client) != 1:
                raise Exception("weird condition, there should only be one large torrent at once")
            
            return large_managed_torrents[0]
        else:
            return None

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

        return load_candidates, load_choices

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
            infohash = completed_torrent['hash']
            info("Handling completed torrent: %s" % completed_torrent['name'])

            ratio = self.server.d.get_ratio(infohash)
            if ratio < self.REQUIRED_RATIO:
                info("Torrent is completed but not seeded to required ratio.  Skipping.")
                continue

            base_path = self.server.d.get_base_path(infohash)
            self.sync_completed_path_to_remote(base_path)
            self.server.d.erase(infohash)

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
            cumulative_incomplete_size += incomplete_torrent['size']

        info("Cumulative size of incomplete items was %d" % cumulative_incomplete_size)
        effective_available_size = self.SPACE_LIMIT - cumulative_incomplete_size

        return effective_available_size

    def filter_out_managed_items_already_in_client(
        self, managed_group, incomplete_group, complete_group
    ):
        # Filter out the managed items that were already loaded
        not_already_loaded = []
        for k, v in managed_group.iteritems():
            if k not in incomplete_group and k not in complete_group:
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
            self.server.load_start(torrent_to_load['torrent_path'])


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