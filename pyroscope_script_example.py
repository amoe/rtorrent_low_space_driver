#! /usr/bin/env python-pyrocore

# Enter the magic kingdom
from pyrocore import config
from pyrocore.scripts import base
from pprint import pprint, pformat

import pdb



class UserScript(base.ScriptBaseWithConfig):
    """
        Just some script you wrote.
    """

    # argument description for the usage information
    ARGS_HELP = "<arg_1>... <arg_n>"

    # ten gigabyte space limit
    SPACE_LIMIT = 10 * (2 ** 30);


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
        print repr(call)


        set_prio = getattr(config.engine._rpc.f, 'set_priority')


        print call(infohash + ":f1")

        file_list = []

        for i in range(file_len):
            id_ = infohash + ":f" + str(i)
            size = call(id_)
#            set_prio(id_, 0)
            
            file_info = {
                "id": id_,
                "size": size,
            }

            file_list.append(file_info)

        file_list.sort(key=lambda x: x['size'])
        pprint(file_list)

        call2 = getattr(config.engine._rpc.d, 'update_priorities')
        call2(infohash)

        self.LOG.info("XMLRPC stats: %s" % proxy)



if __name__ == "__main__":
    base.ScriptBase.setup()
    UserScript().run()


