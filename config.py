import argparse
import configparser
import logging
from logging import debug, info, error, warning, critical
import os
import sys


def parse_arguments(args):
    """Parses arguments and returns a dict with the result.

    Run with '-h' to see available arguments.

    Args:
        args: List of strings.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--log-level', metavar="LEVEL", type=str, help="Log level", default=None)
    parser.add_argument('--config', metavar="FILE", type=str, help='Config file.')
    parser.add_argument('--log-systemd', action='store_true', help='Format logger to run under a systemd unit.')
    parser.add_argument('--log-file', metavar='FILE', type=str, help='Log everything to this file')
    parser.add_argument('rest_args', metavar="ARGS", nargs='*')
    ns = parser.parse_args(args)
    return vars(ns)


def parse_configfile(config_file):
    """Reads configs stored in a config file and returns a dict with the result.

    Values are stored as strings as no assumption is made about the content.
    The config file must contain only one section, called [main].

    Args:
        config_file: Path to file, string.
    """
    cfg = configparser.ConfigParser()
    with open(config_file, 'r') as f:
        cfg.read_file(f)
    return dict(cfg.items('main'))


def start_logger(log_level, log_handler):
    """Starts the root logger.

    Starts the root logger at log_level and using the handlers set in
    log_handler.

    Args:
        log_level: Logger level in string format. Use either
          'DEBUG', 'INFO', 'WARNING', 'ERROR' or 'CRITICAL'
        log_handler: Dictionary containing two keys. Use the following format:
          {log_systemd: boolean, log_file: path_to_file}
          To use the default logging handler set both values to None.
    """
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
        hdl = logging.FileHandler(log_handler.get('log_file'))
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
    """Holds configurations for the current run.

    Attributes:
        arguments: Current run arguments.
        configs: Current run configurations.
    """
    DEFAULT_CONFIG_FILE_PATH = "~/.rtorrent_low_space_driver.cf"

    def __init__(self, args):
        """Inits Configuration with args.

        Args:
            args: strings in list format, with command-line arguments.
        """
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
        """Runs start_logger with arguments retrieved from the current object."""
        log_level = self.arguments.get('log_level') \
                    or self.configs.get('log_level') \
                    or 'INFO'
        log_handler = {'log_systemd': self.arguments.get('log_systemd'),
                       'log_file': self.arguments.get('log_file')}
        start_logger(log_level, log_handler)
