#! /usr/bin/python3

# main test suite

import unittest

class TestThings(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_main(self):
        self.assertEqual(2+2, 4)

if __name__ == "__main__":
    unittest.main()
