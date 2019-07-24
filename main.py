#! /usr/bin/env python3

import driver
import sys
import metadata.libtorrent

if __name__ == "__main__":
    metadata_svc = metadata.libtorrent.LibtorrentMetadataService()
    obj = driver.RtorrentLowSpaceDriver(metadata_svc)
    obj.run(sys.argv[1:])
