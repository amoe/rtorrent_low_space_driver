#! /usr/bin/env python3

import sys

import driver
import config
import metadata

if __name__ == "__main__":
    metadata_svc = metadata.LibtorrentMetadataService()
    cfg = config.MyConfiguration(sys.argv[1:]).configs
    obj = driver.RtorrentLowSpaceDriver(metadata_svc, cfg)
    obj.run()
