#! /usr/bin/python3

# main test suite

import unittest
from main import RtorrentLowSpaceDriver

class TestThings(unittest.TestCase):
    driver = None

    def setUp(self):
        self.driver = RtorrentLowSpaceDriver()

    def tearDown(self):
        pass

    def test_main(self):
        self.assertEqual(2+2, 4)

    def test_build_next_load_group(self):
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
        self.assertEqual(1, len(next_group))
        self.assertEqual("foo", next_group[0]['name'])


if __name__ == "__main__":
    unittest.main()
