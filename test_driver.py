#! /usr/bin/python3

# main test suite

import pytest

import driver
import metadata


@pytest.fixture(scope="module")
def configs_valid():
    obj = {'managed_torrents_directory': 'fake_dir/manages',
           'space_limit': '14551089152',
           'required_ratio': '0',
           'socket_url': 'scgi://fake_dir/.session/rpc.socket',
           'remote_host': 'localhost',
           'remote_path': 'upload'
           }
    return obj


class TestThings:
    def test_sanity(self):
        assert 2+2 == 4

    def test_build_next_load_group(self, configs_valid):
        metadata_svc = metadata.MetadataService()
        self.driver = driver.RtorrentLowSpaceDriver(metadata_svc, configs_valid)

        limit = 4 * 2**20

        candidates = [
            {
                'name': "foo",
                'size': 4 * 2**20
            },
            {
                'name': "bar",
                'size': 4 * 2**20
            }
        ]

        next_group = self.driver.build_next_load_group(candidates, limit)
        assert len(next_group) == 1
        assert "foo" == next_group[0]['name']
