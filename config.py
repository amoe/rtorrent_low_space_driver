import argparse
import configparser
import logging
import os


def parse_arguments(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--log-level', metavar="LEVEL", type=str, help="Log level", default=None)
    parser.add_argument('rest_args', metavar="ARGS", nargs='*')
    ns = parser.parse_args(args)
    return vars(ns)


def parse_configfile():
    cfg = configparser.ConfigParser()
    cfg.read(os.path.expanduser("~/.rtorrent_low_space_driver.cf"))
    return cfg


class MyConfiguration:
    def __init__(self, args):
        self.arguments = parse_arguments(args)
        self.configs = parse_configfile()
