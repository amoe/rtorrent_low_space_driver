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
# When the next group is zero items, the completed list will be full, the torrent will have zero space usage and all priorities will be zero.



class UserScript(base.ScriptBaseWithConfig):
    """
        Just some script you wrote.
    """

    # argument description for the usage information
    ARGS_HELP = "<arg_1>... <arg_n>"

    # five gigabyte space limit
    SPACE_LIMIT = 5 * (2 ** 30);


    def add_options(self):
        """ Add program options.
        """
        super(UserScript, self).add_options()

        # basic options
        ##self.add_bool_option("-n", "--dry-run",
        ##    help="don't do anything, just tell what would happen")


    def mainloop(self):
        """ The main loop.
        """
        # Grab your magic wand
        proxy = config.engine.open()

        # store hash in external file
        infohash = open('hash.txt').read().rstrip()


        # Wave it
        torrents = list(config.engine.items())

        call_idx = getattr(config.engine._rpc.d, 'get_size_files')
        file_len = call_idx(infohash)

        call = getattr(config.engine._rpc.f, 'get_size_bytes')
#        print repr(call)


        set_prio = getattr(config.engine._rpc.f, 'set_priority')
        get_completed_chunks = getattr(config.engine._rpc.f, 'get_completed_chunks')
        get_size_chunks = getattr(config.engine._rpc.f, 'get_size_chunks')
        get_path = getattr(config.engine._rpc.f, 'get_path')
        

#        print call(infohash + ":f1")

        file_list = []

        for i in range(file_len):
            id_ = infohash + ":f" + str(i)
            size = call(id_)
            set_prio(id_, 0)
            path = get_path(id_)
            cmp_chunks = get_completed_chunks(id_)
            size_chunks = get_size_chunks(id_)
#            pprint(cmp_chunks)
#            pprint(size_chunks)

            percentage = int((float(cmp_chunks) / float(size_chunks)) * 100)


            print "%s: %d%%" % (path, percentage)
            
            file_info = {
                "id": id_,
                "size": size,
            }

            file_list.append(file_info)

        file_list.sort(key=lambda x: x['size'])
#        pprint(file_list)

        group = []
        size_so_far = 0

        for file_ in file_list:
            this_size = file_['size']
            if (size_so_far + this_size) > self.SPACE_LIMIT:
                break
            size_so_far += this_size
            group.append(file_)


        for file_ in group:
            set_prio(file_['id'], 1)


        call2 = getattr(config.engine._rpc.d, 'update_priorities')
        call2(infohash)

        self.LOG.info("XMLRPC stats: %s" % proxy)



if __name__ == "__main__":
    base.ScriptBase.setup()
    UserScript().run()


