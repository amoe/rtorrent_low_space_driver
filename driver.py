from logging import debug, info, error, warning
import os
import os.path
from pprint import pformat
import subprocess
import tempfile
import time
import shutil

import rtorrent_xmlrpc
import remotesync


def splitter(data, pred):
    """Split items to two lists according to an evaluating function.

    Args:
        data: List, or any other iterable.
        pred: Evaluating function. When applied to items in 'data' it must
          return either False or True.

    Returns:
        A nested list [[yes], [no]], where [yes] contains all objects that
          evaluated to True, and [no] to False.
    """
    yes, no = [], []
    for d in data:
        if pred(d):
            yes.append(d)
        else:
            no.append(d)
    return [yes, no]


class RtorrentLowSpaceDriver(object):
    """Torrent rotator algorithm.

    This class has one public method, run(), which runs the torrent rotator
    algorithm. And no public attributes.
    """
    def __init__(self, metadata_service, cfg):
        """Inits RtorrentLowSpaceDriver.

        Args:
            metadata_service: A class from metadata.py.
            cfg: configs in dictionary form.
        """
        self.metadata_service = metadata_service

        info("Starting.")
        self.MANAGED_TORRENTS_DIRECTORY = cfg['managed_torrents_directory']
        self.SPACE_LIMIT = int(cfg['space_limit'])
        self.REQUIRED_RATIO = float(cfg['required_ratio'])
        self.SOCKET_URL = cfg['socket_url']

        self.remote_sync_service = remotesync.get_service(**cfg)

        self.server = rtorrent_xmlrpc.SCGIServerProxy(self.SOCKET_URL)

    def run(self):
        """Runs the torrent rotator algorithm."""
        large_torrent = self.check_for_large_managed_torrents()

        if large_torrent is not None:
            info("Detected incomplete & already loaded large torrent.  Switching to large strategy.")
            info("Torrent is %s" % pformat(large_torrent))
            load_new_p = self.handle_large_torrent_strategy(large_torrent)
            if load_new_p:
                # Although we *could* load a new torrent here, it's easier for
                # algorithmic purposes to just not and wait until the next run.
                info("Detected completed large torrent.  Clearing until next run.")
                self.purge_torrent(large_torrent)

            info("Large strategy completed successfully.")
        else:
            info("Using small torrents strategy per default.")
            load_candidates, load_choices = self.handle_small_torrents_strategy()
            info("Small torrents strategy finished.")
            if not load_choices:
                if load_candidates:
                    if self.get_incomplete_managed_torrents() or self.insufficiently_seeded_managed_torrents_exist():
                        info("Waiting for incomplete torrents to complete and seed before switching to large strategy.")
                    else:
                        info("Large torrents blocked by small strategy.  Switching to large strategy.")
                        by_size = sorted(load_candidates, key=lambda t: t['size'])

                        # slice off just the first item
                        self.load_torrents(by_size[:1])
                        self.handle_large_torrent_strategy(by_size[0])
                        info("First run of large strategy completed successfully.")
                else:
                    info(
                        "No candidates to load.  Either all torrents are already loaded, or there are no torrents in "
                        "the managed directory.")
                    info("For you to verify, said managed torrent list is %s" % pformat(
                        self.build_managed_torrents_list()))
                    info("Now quietly exiting successfully.")
            else:
                info("Small strategy succeeded.  See you next time!")

        info("Done.")

    # SMALL TORRENT STRATEGY

    def check_for_large_managed_torrents(self):
        managed_torrents_in_client = self.get_incomplete_managed_torrents()
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

    def insufficiently_seeded_managed_torrents_exist(self):
        managed_torrents = self.build_managed_torrents_list()
        rt_complete, rt_incomplete = self.get_torrents_from_rtorrent()
        managed_and_complete = [
            managed_torrents[t] for t in rt_complete
            if t in managed_torrents
        ]

        for t in managed_and_complete:
            ratio = self.get_ratio_of_torrent(t['hash'])
            info("Scanned ratio as %f" % ratio)

            if ratio < self.REQUIRED_RATIO:
                info("Determined that insufficiently seeded torrents exist")
                return True

        # It's weird, because by the stage this is called, we should have 
        # already synced and removed them.
        # Which kind of begs the question as to why this method exists, but
        # we're going to ignore that question for now.
        info("Sufficiently seeded torrents exists, which tbh is kind of weird.")
        return False

    def get_incomplete_managed_torrents(self):
        managed_torrents = self.build_managed_torrents_list()
        rt_complete, rt_incomplete = self.get_torrents_from_rtorrent()

        managed_torrents_in_client = [
            managed_torrents[t] for t in rt_incomplete
            if t in managed_torrents
        ]

        debug("Managed torrents in client: %s" % pformat(managed_torrents_in_client))

        return managed_torrents_in_client

    def handle_small_torrents_strategy(self):
        managed_torrents = self.build_managed_torrents_list()
        rt_complete, rt_incomplete = self.get_torrents_from_rtorrent()
        self.sync_and_remove(
            [managed_torrents[t] for t in rt_complete
             if t in managed_torrents]
        )

        # Update the list of torrents to account for removals.  Effective
        # space should consider both completed and incomplete torrents,
        # because torrents that didn't seed yet sit around consuming space
        # for quite a while.
        rt_complete, rt_incomplete = self.get_torrents_from_rtorrent()
        effective_space = self.compute_effective_available_space(
            [managed_torrents[t] for t in (rt_incomplete + rt_complete)
             if t in managed_torrents]
        )
        info("Available size to load is %d", effective_space)

        load_candidates = self.filter_out_managed_items_already_in_client(
            managed_torrents, rt_incomplete, rt_complete
        )
        load_choices = self.build_next_load_group(
            load_candidates, effective_space
        )

        info("Decided to load these torrents: %s" % pformat(load_choices))
        self.load_torrents(load_choices)

        return load_candidates, load_choices

    # make lookup table for torrents, should be a set
    def build_managed_torrents_list(self):
        managed_torrents = {}
        for torrent in os.listdir(self.MANAGED_TORRENTS_DIRECTORY):
            full_path = os.path.join(self.MANAGED_TORRENTS_DIRECTORY, torrent)

            try:
                t_info = self.metadata_service.torrent_info(full_path)
            except RuntimeError as e:
                error("Cannot read torrent info for '%s', perhaps corrupted" % full_path)
                raise e

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

            ratio = self.get_ratio_of_torrent(infohash)
            info("Ratio of completed torrent was determined as %f" % ratio)

            if ratio < self.REQUIRED_RATIO:
                info("Torrent is completed but not seeded to required ratio.  Skipping.")
                continue

            base_path = self.server.d.base_path(infohash)
            base_filename = self.server.d.base_filename(infohash)
            self.remote_sync_service.sync_path(base_path, base_filename)
            self.purge_torrent(completed_torrent)

    # Purge a torrent, this means remove it from rtorrent, also delete the
    # local files, and remove the torrent from the group of managed torrents.
    # Takes a torrent object.
    def purge_torrent(self, completed_torrent):
        # XXX: This method could probably use some caching
        managed_torrents = self.build_managed_torrents_list()
        infohash = completed_torrent['hash']
        base_path = self.server.d.base_path(infohash)

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

    # "Cumulative used size" here means the actual size used by completed
    # torrents, plus the size projected to be used by the currently loaded
    # incomplete torrents.
    def compute_effective_available_space(self, torrent_list):
        # Count incomplete torrents
        cumulative_used_size = 0
        for torrent in torrent_list:
            cumulative_used_size += torrent['size']

        info("Cumulative used and incomplete size was %d" % cumulative_used_size)
        effective_available_size = self.SPACE_LIMIT - cumulative_used_size

        return effective_available_size

    def filter_out_managed_items_already_in_client(
        self, managed_group, incomplete_group, complete_group
    ):
        # Filter out the managed items that were already loaded
        not_already_loaded = []
        for k, v in managed_group.items():
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
        start_function = getattr(self.server, 'load.start')

        for torrent_to_load in torrent_paths:
            # For some reason, it needs to have a blank string as the first
            # target.  See <https://github.com/rakshasa/rtorrent/issues/627>
            start_function('', torrent_to_load['torrent_path'])

    # LARGE TORRENT STRATEGY

    # The large torrent strategy always works on a single torrent at a time.
    # This has to already have been loaded.
    # Returns a boolean indicating if this torrent should be removed, and a
    # new large torrent should be loaded.
    def handle_large_torrent_strategy(self, torrent):
        infohash = torrent['hash']

        realpath = self.server.d.directory(infohash)

        info("Managing large torrent: %s" % torrent['name'])

        self.stop_torrent(infohash)
        local_completed_files = self.check_for_local_completed_files(infohash)
        info("Locally completed files: %s" % pformat(local_completed_files))

        self.remote_sync_service.maybe_create_directory(realpath)

        if local_completed_files:
            self.sync_completed_files_to_remote(realpath, local_completed_files)
        else:
            info("Nothing completed locally, so not syncing anything.")

        remote_completed_list = self.remote_sync_service.list_files(realpath)
        debug("Remotely completed files: %s" % pformat(remote_completed_list))

        self.remove_completed_files(realpath, local_completed_files)
        self.set_all_files_to_zero_priority(infohash)

        next_group = self.generate_next_group(infohash, remote_completed_list)
        debug("Next group: %s" % pformat(next_group))

        if next_group:
            self.set_priority(infohash, [x['id'] for x in next_group], 1)
            self.start_torrent(infohash)
        else:
            is_completed = \
                self.is_large_torrent_remotely_completed(
                    infohash, remote_completed_list
                )
            if is_completed:
                info("We decided that this torrent is completed.")
                return True
            else:
                info("Not yet completed, but resuming torrent with no new files.")
                self.start_torrent(infohash)
                return False

    # returns list of locally completed files as IDs
    def check_for_local_completed_files(self, infohash):
        completed_list = []

        size_files = self.server.d.size_files(infohash)

        for i in range(size_files):
            id_ = "%s:f%d" % (infohash, i)
            path = self.server.f.path(id_)
            debug("Torrent path: %s" % path)
            done = self.server.f.completed_chunks(id_)
            total = self.server.f.size_chunks(id_)
            priority = self.server.f.priority(id_)

            if done == total and priority > 0:
                completed_list.append(self.server.f.path(id_))

        return completed_list

    def stop_torrent(self, infohash):
        self.server.d.stop(infohash)

    def sync_completed_files_to_remote(self, realpath, completed_files):
        with tempfile.NamedTemporaryFile(
            suffix=".lst", prefix="transfer_list-", delete=False
        ) as transfer_list:
            tmpfile_path = transfer_list.name

            for path in completed_files:
                transfer_list.write(bytes(path + "\n", 'utf8'))

        self.remote_sync_service.sync_files_from_filelist(realpath, tmpfile_path)
        os.remove(transfer_list.name)

    def remove_completed_files(self, realpath, completed_files):
        for path in completed_files:
            self._zero_out_file(os.path.join(realpath, path))
        subprocess.check_call(["sync"])

    def _zero_out_file(self, path):
        open(path.encode('utf8'), 'w').close()

    def is_large_torrent_remotely_completed(self, infohash, remote_completed_list):
        file_len = self.server.d.size_files(infohash)
        debug("Files in torrent: %d" % file_len)
        debug("Remotely completed files: %d" % len(remote_completed_list))

        # Sometimes the remote can be more, because rsync can leave temporaries
        # around with weird suffixes.  There's no real way to control this, and
        # it's too dangerous to use --delete, so we just leave them there.
        return len(remote_completed_list) >= file_len

    def set_all_files_to_zero_priority(self, infohash):
        id_list = []
        file_len = self.server.d.size_files(infohash)

        for i in range(file_len):
            id_list.append("%s:f%d" % (infohash, i))

        self.set_priority(infohash, id_list, 0)

    def set_priority(self, infohash, ids, priority):
        for id_ in ids:
            self.server.f.priority.set(id_, priority)
        self.server.d.update_priorities(infohash)

    # Check for the situation where, under the large torrents strategy, a large
    # torrent has a single file within it that breaches the global space limit.
    # The only real way to respond to this is for the user to manually increase
    # the space limit.
    def check_for_intractable_files(self, file_list):
        limit = self.SPACE_LIMIT

        for file_ in file_list:
            path = file_['path']
            file_size = file_['size']
            if file_size > self.SPACE_LIMIT:
                new_suggested_size = file_size + (10 * 2**20)
                warning(
                    f"Torrent contains file that is intractable within size limit {limit}!"
                )
                warning(
                    f"Intractable file: {path}"
                )
                warning(
                    f"Size required: {file_size}"
                )
                warning(
                    f"Suggest raising limit to {new_suggested_size}."
                )

    def generate_next_group(self, infohash, exclude_list):
        file_len = self.server.d.size_files(infohash)
        file_list = []
        for i in range(file_len):
            id_ = "%s:f%d" % (infohash, i)
            size = self.server.f.size_bytes(id_)
            path = self.server.f.path(id_)
            datum = {
                'id': id_, 'size': size, 'path': path
            }
            file_list.append(datum)

        debug("File list was: %s", pformat(file_list))

        self.check_for_intractable_files(file_list)

        # filter out items existing on remote
        filtered_items = [x for x in file_list if x['path'] not in exclude_list]

        info("Filtered list was: %s", pformat(file_list))

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

    def start_torrent(self, infohash):
        while True:
            self.server.d.start(infohash)
            time.sleep(1)
            if self.server.d.is_active(infohash) == 1:
                break
            else:
                error("failed to resume torrent, retrying")
                self.server.d.stop(infohash)
                time.sleep(1)

    # For some reason the XMLRPC interface returns the ratio as an i8, so
    # convert it to the more regular floating point ratio.
    def get_ratio_of_torrent(self, infohash):
        ratio = self.server.d.ratio(infohash)
        float_ratio = ratio / 1000.0
        return float_ratio
