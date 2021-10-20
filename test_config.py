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
def cfgfile_valid(dirs):
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
def cfgfile_repeated_item(dirs):
    string = \
        f'''[main]
    managed_torrents_directory = {dirs['managed']}
    space_limit = 14551089152
    required_ratio = 0
    required_ratio = 1
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
def cfgfile_unexpected_item(dirs):
    string = \
        f'''[main]
    managed_torrents_directory = {dirs['managed']}
    space_limit = 14551089152
    required_ratio = 0
    socket_url = scgi://{dirs['rtorrent']}/.session/rpc.socket
    remote_host = localhost
    remote_path = upload
    unexpected_item = test'''

    p = dirs['config'] / 'rtorrent_low_space_driver.cf'
    p.touch()
    p.write_text(string)
    yield p
    os.remove(p)


@pytest.fixture
def arg_valid_cfgfile_valid(cfgfile_valid):
    return [f'--config={cfgfile_valid}']


@pytest.fixture
def arg_debug_cfgfile_valid(cfgfile_valid):
    return [f'--config={cfgfile_valid}', '--log-level=DEBUG']


@pytest.fixture
def arg_positional_cfgfile_valid(cfgfile_valid):
    return [f'--config={cfgfile_valid}', 'a.torrent b.torrent']


@pytest.fixture
def arg_valid_cfgfile_repeated_item(cfgfile_repeated_item):
    return [f'--config={cfgfile_repeated_item}']


@pytest.fixture
def arg_valid_cfgfile_unexpected_item(cfgfile_unexpected_item):
    return [f'--config={cfgfile_unexpected_item}']


class TestConfiguration:
    # These test for a scenario where valid configs where passed to the class
    # We expect the class to run fine.
    def test_constructor_arg_valid_cfgfile_valid(self, arg_valid_cfgfile_valid):
        # Tests the constructor against a valid argument and valid configfile
        a = config.Configuration(arg_valid_cfgfile_valid).configs
        assert len(a.items('main')) == 6
        assert config.logging.getLogger().getEffectiveLevel() == 20

    def test_constructor_arg_debug_cfgfile_valid(self, arg_debug_cfgfile_valid):
        # Tests the constructor against a valid argument and valid configfile
        # Running in a non-default log-level, DEBUG
        a = config.Configuration(arg_debug_cfgfile_valid).configs
        assert len(a.items('main')) == 6
        assert config.logging.getLogger().getEffectiveLevel() == 10

    # These test for a scenario where non-critical misconfigs where passed to the class
    # We expect the class to run fine. At the moment the user will not be notified.
    def test_constructor_arg_valid_config_file_unexpecteditem(self, arg_valid_cfgfile_unexpected_item):
        # Tests the constructor against a valid argument and a configfile with an unexpected item
        a = config.Configuration(arg_valid_cfgfile_unexpected_item).configs
        assert len(a.items('main')) == 7

    # These test for a scenario where critical misconfigs where passed to the class
    # We expect the constructor to raise an Error somehow and exit.
    def test_constructor_arg_valid_cfgfile_repeated_item(self, arg_valid_cfgfile_repeated_item):
        # Tests the constructor against a valid argument and an invalid configfile (repeated item)
        with pytest.raises(configparser.DuplicateOptionError):
            config.Configuration(arg_valid_cfgfile_repeated_item)

    def test_constructor_arg_valid_noconfigfile(self, caplog):
        args = ['--config= ']
        config.Configuration.DEFAULT_CONFIG_FILE_PATH = ' '
        # Tests the constructor against a situation where no configfile is found
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            config.Configuration(args)
            assert caplog.records[-1].levelname == 'CRITICAL'
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
