import errno
import unittest

from night_rally import night_rally


class DummySocketConnector:
    def __init__(self, port_listening=None):
        self.port_listening = port_listening if port_listening else False

    def socket(self):
        return self

    def connect_ex(self, host_port):
        if self.port_listening:
            return 0
        else:
            return errno.ECONNREFUSED

    def close(self):
        pass


class WaitUntilPortFreeTests(unittest.TestCase):
    multi_host_string = "192.168.14.3:9200,192.168.14.4:9200,192.168.14.5:9200".split(",")
    single_host_string = "192.168.2.3:9200".split(",")
    single_host_no_port = "192.168.2.4"

    def test_fail_if_es_http_port_listening(self):
        with self.assertRaises(night_rally.RemotePortNotFree):
            night_rally.wait_until_port_is_free(
                WaitUntilPortFreeTests.multi_host_string,
                connector=DummySocketConnector(port_listening=True),
                wait_time=0)

        with self.assertRaises(night_rally.RemotePortNotFree):
            self.assertFalse(night_rally.wait_until_port_is_free(
                WaitUntilPortFreeTests.single_host_string,
                connector=DummySocketConnector(port_listening=True),
                wait_time=0))

    def test_succeed_if_es_http_port_available(self):
        self.assertTrue(night_rally.wait_until_port_is_free(
            WaitUntilPortFreeTests.multi_host_string,
            connector=DummySocketConnector(port_listening=False),
            wait_time=0))

        self.assertTrue(night_rally.wait_until_port_is_free(
            WaitUntilPortFreeTests.single_host_string,
            connector=DummySocketConnector(port_listening=False),
            wait_time=0))

    def test_fail_if_port_missing_from_target_host(self):
        with self.assertRaises(night_rally.RemotePortNotDefined):
            night_rally.wait_until_port_is_free(
                WaitUntilPortFreeTests.single_host_no_port,
                connector=DummySocketConnector(port_listening=False),
                wait_time=0)
