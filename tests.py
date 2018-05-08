import datetime
import unittest
import errno

from unittest import mock


if __name__ == "__main__" and __package__ is None:
    __package__ = "night_rally"

import night_rally


class RecordingSystemCall:
    def __init__(self, return_value):
        self.calls = []
        self.return_value = return_value

    def __call__(self, *args, **kwargs):
        self.calls.append(*args)
        return self.return_value


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


class VersionsTests(unittest.TestCase):
    def test_finds_components_for_valid_version(self):
        self.assertEqual((5, 0, 3, None), night_rally.components("5.0.3"))
        self.assertEqual((5, 0, 3, "SNAPSHOT"), night_rally.components("5.0.3-SNAPSHOT"))

    def test_components_ignores_invalid_versions(self):
        with self.assertRaises(ValueError) as ctx:
            night_rally.components("5.0.0a")
        self.assertEqual("version string '5.0.0a' does not conform to pattern '^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$'", ctx.exception.args[0])


class WaitUntilPortFreeTests(unittest.TestCase):
    multi_host_string = "192.168.14.3:39200,192.168.14.4:39200,192.168.14.5:39200".split(",")
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


class NightRallyTests(unittest.TestCase):
    def test_sanitize(self):
        self.assertEqual("lucene-7-upgrade", night_rally.sanitize("Lucene 7 Upgrade"))
        self.assertEqual("lucene-7-upgrade", night_rally.sanitize("lucene-7-upgrade"))
        self.assertEqual("elasticsearch-6_0_0-alpha1-docker", night_rally.sanitize("Elasticsearch 6.0.0-alpha1 Docker"))

    def test_join(self):
        self.assertEqual("env:bare,name:test", night_rally.join_nullables("env:bare", None, "name:test"))
        self.assertEqual("name:test", night_rally.join_nullables(None, "name:test"))
        self.assertEqual("", night_rally.join_nullables(None))

    @mock.patch('night_rally.wait_until_port_is_free', return_value=True)
    def test_run_two_challenges_successfully(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "combinations": [
                    {
                        "name": "geonames-defaults",
                        "challenge": "append-no-conflicts",
                        "car": "defaults",
                        "car-params": "verbose_iw_logging_enabled:true"
                    },
                    {
                        "name": "geonames-4g",
                        "challenge": "append-no-conflicts",
                        "car": "4gheap"
                    }
                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        params = [night_rally.StandardParams(night_rally.NightlyCommand.CONFIG_NAME, start_date, {"env": "bare"})]
        cmd = night_rally.NightlyCommand(params, start_date)
        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"defaults\" --user-tag=\"env:bare,name:geonames-defaults\" --car-params=\"verbose_iw_logging_enabled:true\" "
                "--pipeline=\"from-sources-complete\" --revision=\"@2016-01-01T00:00:00Z\"",

                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"4gheap\" --user-tag=\"env:bare,name:geonames-4g\" --pipeline=\"from-sources-skip-build\" "
                "--revision=\"@2016-01-01T00:00:00Z\""
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.wait_until_port_is_free', return_value=True)
    def test_run_two_tracks_successfully(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "combinations": [
                    {
                        "name": "geonames-defaults",
                        "challenge": "append-no-conflicts",
                        "car": "defaults"
                    }
                ]
            },
            {
                "track": "percolator",
                "combinations": [
                    {
                        "name": "percolator-4g",
                        "challenge": "append-no-conflicts",
                        "car": "4gheap"
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 10, 1)
        params = [night_rally.StandardParams(night_rally.NightlyCommand.CONFIG_NAME, start_date, {"env": "bare"})]
        cmd = night_rally.NightlyCommand(params, start_date)
        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"defaults\" --user-tag=\"env:bare,name:geonames-defaults\" --pipeline=\"from-sources-complete\" "
                "--revision=\"@2016-10-01T00:00:00Z\"",

                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track=\"percolator\" --challenge=\"append-no-conflicts\" "
                "--car=\"4gheap\" --user-tag=\"env:bare,name:percolator-4g\" --pipeline=\"from-sources-skip-build\" "
                "--revision=\"@2016-10-01T00:00:00Z\""
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.wait_until_port_is_free', return_value=True)
    def test_run_adhoc_benchmark(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "combinations": [
                    {
                        "name": "geonames-defaults",
                        "challenge": "append-no-conflicts",
                        "car": "defaults"
                    }
                ]
            },
            {
                "track": "percolator",
                "combinations": [
                    {
                        "name": "percolator-4g",
                        "challenge": "append-no-conflicts",
                        "car": "4gheap"
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 10, 1)
        params = [night_rally.StandardParams("lucene-7", start_date, {"env": "bare"})]
        cmd = night_rally.AdHocCommand(params, "66202dc")

        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"lucene-7\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"defaults\" --user-tag=\"env:bare,name:geonames-defaults\" --pipeline=\"from-sources-complete\" "
                "--revision=\"66202dc\"",

                "rally --skip-update --configuration-name=\"lucene-7\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track=\"percolator\" --challenge=\"append-no-conflicts\" "
                "--car=\"4gheap\" --user-tag=\"env:bare,name:percolator-4g\" --pipeline=\"from-sources-skip-build\" --revision=\"66202dc\""
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.wait_until_port_is_free', return_value=True)
    def test_run_release_benchmark_without_plugins(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "combinations": [
                    {
                        "name": "geonames-defaults",
                        "challenge": "append-no-conflicts",
                        "car": "defaults"
                    },
                    {
                        "name": "geonames-4g",
                        "challenge": "append-no-conflicts",
                        "car": "4gheap"
                    }
                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        params = [night_rally.StandardParams("release", start_date, {"env": "bare"})]
        cmd = night_rally.ReleaseCommand(params, None, "5.3.0")
        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"defaults\" --user-tag=\"env:bare,name:geonames-defaults\" --distribution-version=\"5.3.0\" "
                "--pipeline=\"from-distribution\"",

                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"4gheap\" --user-tag=\"env:bare,name:geonames-4g\" --distribution-version=\"5.3.0\" "
                "--pipeline=\"from-distribution\""
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.wait_until_port_is_free', return_value=True)
    def test_run_release_benchmark_with_plugins(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "combinations": [
                    {
                        "name": "geonames-defaults",
                        "challenge": "append-no-conflicts",
                        "car": "defaults"
                    },
                    {
                        "name": "geonames-4g",
                        "challenge": "append-no-conflicts",
                        "car": "4gheap"
                    },
                    # should not run this combination - because we filter x-pack configs
                    {
                        "name": "geonames-4g-with-x-pack",
                        "challenge": "append-no-conflicts",
                        "car": "4gheap",
                        "x-pack": ["security"]
                    },

                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        params = [night_rally.StandardParams("release", start_date, {"env": "x-pack"})]
        cmd = night_rally.ReleaseCommand(params, ["security", "monitoring"], "5.3.0")

        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"defaults\" --user-tag=\"env:x-pack,name:geonames-defaults,x-pack:true\" "
                "--client-options=\"timeout:60,use_ssl:true,verify_certs:false,basic_auth_user:'rally',"
                "basic_auth_password:'rally-password'\" --elasticsearch-plugins=\"x-pack:security,monitoring\" "
                "--track-params=\"cluster_health:'yellow'\" --distribution-version=\"5.3.0\" --pipeline=\"from-distribution\"",

                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"4gheap\" --user-tag=\"env:x-pack,name:geonames-4g,x-pack:true\" --client-options=\"timeout:60,use_ssl:true"
                ",verify_certs:false,basic_auth_user:'rally',basic_auth_password:'rally-password'\" "
                "--elasticsearch-plugins=\"x-pack:security,monitoring\" --track-params=\"cluster_health:'yellow'\" "
                "--distribution-version=\"5.3.0\" --pipeline=\"from-distribution\"",
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.wait_until_port_is_free', return_value=True)
    def test_run_release_benchmark_with_x_pack_module(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "combinations": [
                    {
                        "name": "geonames-defaults",
                        "challenge": "append-no-conflicts",
                        "car": "defaults"
                    },
                    {
                        "name": "geonames-4g",
                        "challenge": "append-no-conflicts",
                        "car": "4gheap"
                    },
                    # should not run this combination - because we filter x-pack configs
                    {
                        "name": "geonames-4g-with-x-pack",
                        "challenge": "append-no-conflicts",
                        "car": "4gheap",
                        "x-pack": "security"
                    },

                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        params = [night_rally.StandardParams("release", start_date, {"env": "x-pack"})]
        # 6.3.0 is the first version to include x-pack as a module
        cmd = night_rally.ReleaseCommand(params, ["security", "monitoring"], "6.3.0")

        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"defaults,x-pack-security,x-pack-monitoring\" --user-tag=\"env:x-pack,name:geonames-defaults,x-pack:true\" "
                "--client-options=\"timeout:60,use_ssl:true,verify_certs:false,basic_auth_user:'rally',"
                "basic_auth_password:'rally-password'\" --track-params=\"cluster_health:'yellow'\" --distribution-version=\"6.3.0\" "
                "--pipeline=\"from-distribution\"",

                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"4gheap,x-pack-security,x-pack-monitoring\" --user-tag=\"env:x-pack,name:geonames-4g,x-pack:true\" "
                "--client-options=\"timeout:60,use_ssl:true,verify_certs:false,basic_auth_user:'rally',"
                "basic_auth_password:'rally-password'\" --track-params=\"cluster_health:'yellow'\" --distribution-version=\"6.3.0\" "
                "--pipeline=\"from-distribution\"",
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.wait_until_port_is_free', return_value=True)
    def test_run_docker_benchmark(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "combinations": [
                    {
                        "name": "geonames-defaults",
                        "challenge": "append-no-conflicts",
                        "car": "defaults"
                    },
                    {
                        "name": "geonames-4g",
                        "challenge": "append-no-conflicts",
                        "car": "4gheap"
                    }
                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        params = [night_rally.StandardParams("release", start_date, {"env": "docker"})]
        cmd = night_rally.DockerCommand(params, "5.3.0")

        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"defaults\" --user-tag=\"env:docker,name:geonames-defaults\" --track-params=\"cluster_health:'yellow'\" "
                "--distribution-version=\"5.3.0\" --pipeline=\"docker\"",

                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"4gheap\" --user-tag=\"env:docker,name:geonames-4g\" --track-params=\"cluster_health:'yellow'\" "
                "--distribution-version=\"5.3.0\" --pipeline=\"docker\""
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.wait_until_port_is_free', return_value=True)
    def test_run_continues_on_error(self, mocked_wait_until_port_is_free):
        self.maxDiff = None
        system_call = RecordingSystemCall(return_value=True)

        tracks = [
            {
                "track": "geonames",
                "combinations": [
                    {
                        "name": "geonames-defaults",
                        "challenge": "append-no-conflicts",
                        "car": "defaults"
                    }
                ]
            },
            {
                "track": "percolator",
                "combinations": [
                    {
                        "name": "percolator-4g",
                        "challenge": "append-no-conflicts",
                        "car": "4gheap"
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 10, 1)
        params = [night_rally.StandardParams(night_rally.NightlyCommand.CONFIG_NAME, start_date, {"env": "bare"})]
        cmd = night_rally.NightlyCommand(params, start_date)
        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)

        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
                "--car=\"defaults\" --user-tag=\"env:bare,name:geonames-defaults\" --pipeline=\"from-sources-complete\" "
                "--revision=\"@2016-10-01T00:00:00Z\"",

                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track=\"percolator\" --challenge=\"append-no-conflicts\" "
                "--car=\"4gheap\" --user-tag=\"env:bare,name:percolator-4g\" --pipeline=\"from-sources-skip-build\" "
                "--revision=\"@2016-10-01T00:00:00Z\""
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.wait_until_port_is_free', return_value=True)
    def test_run_with_telemetry(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "combinations": [
                    {
                        "name": "geonames-defaults",
                        "challenge": "append-no-conflicts",
                        "car": "defaults"
                    }
                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        params = [
            night_rally.TelemetryParams(
                telemetry="jfr,gc,jit",
                telemetry_params="recording-template:profile"
            ),
            night_rally.StandardParams(night_rally.NightlyCommand.CONFIG_NAME, start_date, {"env": "bare"})]

        cmd = night_rally.NightlyCommand(params, start_date)

        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(1, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --telemetry=\"jfr,gc,jit\" --telemetry-params=\"recording-template:profile\" "
                "--configuration-name=\"nightly\" --quiet --target-host=\"localhost\" --effective-start-date=\"2016-01-01 00:00:00\" "
                "--track=\"geonames\" --challenge=\"append-no-conflicts\" --car=\"defaults\" --user-tag=\"env:bare,name:geonames-defaults\""
                " --pipeline=\"from-sources-complete\" --revision=\"@2016-01-01T00:00:00Z\""
            ]
            ,
            system_call.calls
        )


if __name__ == '__main__':
    unittest.main()
