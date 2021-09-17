import pytest

import configparser
import os

import config


@pytest.fixture
def dirs(tmp_path):
    keys = ['config', 'managed', 'rtorrent', 'remote']
    values = [(tmp_path / key) for key in keys]
    [value.mkdir() for value in values]
    d = dict(zip(keys, values))
    yield d
    [value.rmdir() for value in values]


@pytest.fixture()
def config_file_valid(dirs):
    string = \
        f'''[main]
    managed_torrents_directory = {dirs['managed']}
    space_limit = 14551089152
    required_ratio = 0
    socket_url = scgi://{dirs['rtorrent']}/.session/rpc.socket
    remote_host = localhost
    remote_path = upload'''

    p = dirs['config'] / 'rtorrent_low_space_driver.cf'
    p.touch()
    p.write_text(string)
    yield p
    os.remove(p)


@pytest.fixture
def config_file_repeated_item(dirs):
    string = \
        f'''[main]
    managed_torrents_directory = {dirs['managed']}
    space_limit = 14551089152
    required_ratio = 0
    required_ratio = 1
    service=test
    socket_url = scgi://{dirs['rtorrent']}/.session/rpc.socket
    remote_host = localhost
    remote_host = localhost2
    remote_path = upload'''

    p = dirs['config'] / 'rtorrent_low_space_driver.cf'
    p.touch()
    p.write_text(string)
    yield p
    os.remove(p)


@pytest.fixture
def argument_valid(config_file_valid):
    return [f'--config={config_file_valid}']


@pytest.fixture
def argument_debug(config_file_valid):
    return [f'--config={config_file_valid}', '--log-level=DEBUG']


@pytest.fixture
def argument_positional(config_file_valid):
    return [f'--config={config_file_valid}', 'a.torrent b.torrent']


@pytest.fixture
def argument_config_file_repeated_item(config_file_repeated_item):
    return [f'--config={config_file_repeated_item}']


class TestMyConfiguration:
    def test_constructor_argument_valid(self, argument_valid):
        # Tests the constructor against a valid argument and valid configfile
        a = config.Configuration(argument_valid).configs
        assert len(a.items('main')) == 6
        assert config.logging.getLogger().getEffectiveLevel() == 20

    def test_constructor_argument_debug(self, argument_debug):
        # Tests the constructor against a valid argument and valid configfile
        # Running in a non-default log-level, DEBUG
        a = config.Configuration(argument_debug).configs
        assert len(a.items('main')) == 6
        assert config.logging.getLogger().getEffectiveLevel() == 10

    def test_init_repeateditem(self, argument_config_file_repeated_item):
        # Tests the constructor against a valid argument and an invalid configfile
        with pytest.raises(configparser.DuplicateOptionError):
            config.Configuration(argument_config_file_repeated_item)

    def test_init_noconfig(self, caplog):
        args = ['--config= ']
        config.Configuration.DEFAULT_CONFIG_FILE_PATH = ' '
        # Tests the constructor against a situation where no configfile is found
        with pytest.raises(SystemExit):
            config.Configuration(args)
            assert caplog.records[-1].levelname == 'CRITICAL'
