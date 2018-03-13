#! /usr/bin/env python3

import driver
import sys

if __name__ == "__main__":
    obj = driver.RtorrentLowSpaceDriver()
    obj.run(sys.argv[1:])
