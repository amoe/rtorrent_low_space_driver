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


def start_logger(ns, cfg):
    log_level = ns.get('log_level') or cfg.get('main', 'log_level', fallback='INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(levelname)8s - %(name)s - %(message)s"
    )


class MyConfiguration:
    def __init__(self, args):
        self.arguments = parse_arguments(args)
        self.configs = parse_configfile()

        start_logger(self.arguments, self.configs)
