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
    parser.add_argument('--log-systemd', action='store_true', help='Format logger to run under a systemd unit.')
    parser.add_argument('--log-file', metavar='FILE', type=str, help='Log everything to this file')
    parser.add_argument('rest_args', metavar="ARGS", nargs='*')
    ns = parser.parse_args(args)
    return vars(ns)


def parse_configfile(config_file):
    """Parse configurations stored in the file.

    :type config_file: str
    """
    cfg = configparser.ConfigParser()
    with open(config_file, 'r') as f:
        cfg.read_file(f)
    return dict(cfg.items('main'))


def start_logger(log_level, log_handler):
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    # Set log formatter and handlers
    base_format = "%(levelname)8s - %(message)s"
    if log_handler.get('log_systemd'):
        hdl = logging.StreamHandler()
        fmt = logging.Formatter(base_format)
        hdl.setFormatter(fmt)
        root_logger.addHandler(hdl)
    if log_handler.get('log_file'):
        hdl = logging.FileHandler(os.path.expanduser(log_handler.get('log_file')))
        fmt = logging.Formatter("%(asctime)s - " + base_format)
        hdl.setFormatter(fmt)
        root_logger.addHandler(hdl)
    if not log_handler.get('log_systemd') and \
            not log_handler.get('log_file'):
        hdl = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s - " + base_format)
        hdl.setFormatter(fmt)
        root_logger.addHandler(hdl)


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
        """Passes parameters to start_logger from class instance."""
        log_level = self.arguments.get('log_level') \
                    or self.configs.get('log_level') \
                    or 'INFO'
        log_handler = {'log_systemd': self.arguments.get('log_systemd'),
                       'log_file': self.arguments.get('log_file')}
        start_logger(log_level, log_handler)
