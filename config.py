import argparse
import configparser
import logging
from logging import debug, info, error, warning, critical
import os
import sys


def parse_arguments(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--log-level', metavar="LEVEL", type=str, help="Log level", default=None)
    parser.add_argument('--config', metavar="FILE", type=str, help='Config file.')
    parser.add_argument('rest_args', metavar="ARGS", nargs='*')
    ns = parser.parse_args(args)
    return vars(ns)


def parse_configfile(config_file):
    cfg = configparser.ConfigParser()
    with open(config_file, 'r') as f:
        cfg.read_file(f)
    return dict(cfg.items('main'))


def start_logger(log_level):
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    # Set log formatter and handlers
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)8s - %(name)s - %(message)s")
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)


class Configuration:
    DEFAULT_CONFIG_FILE_PATH = "~/.rtorrent_low_space_driver.cf"

    def __init__(self, args):
        self.arguments = {}
        self.configs = {}

        self.arguments = parse_arguments(args)
        try:
            self._config_file_path = self.arguments.get('config') or self.DEFAULT_CONFIG_FILE_PATH
            self.configs = parse_configfile(os.path.expanduser(self._config_file_path))
        except FileNotFoundError:
            self.set_logger()
            critical('Config file not found! Exiting.')
            sys.exit(1)

        self.set_logger()

    def set_logger(self):
        log_level = self.arguments.get('log_level', None) \
                    or self.configs.get('log_level', None) \
                    or 'INFO'
        start_logger(log_level)
