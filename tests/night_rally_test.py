import datetime
import unittest
import errno
import random
import os

from collections import OrderedDict
from unittest import mock
from night_rally import night_rally


def get_random_race_configs_id():
    race_configs_ids = ["resources/race-configs-group-1.json", "resources/race-configs-group-2.json", "/foo/bar/some_adhoc_conffile.json"]
    return random.choice(race_configs_ids)


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
        self.assertEqual("version string '5.0.0a' does not conform to pattern "+r"'^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$'", ctx.exception.args[0])


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


class CommonCliParamsTests(unittest.TestCase):
    default_mode = "nightly"
    default_version = "master"
    default_release_license = "oss"
    default_release_x_pack_components = ""

    def test_parses_defaults(self):
        race_configs_id = get_random_race_configs_id()

        common_cli_params = night_rally.CommonCliParams(
            mode=CommonCliParamsTests.default_mode,
            configuration_name="nightly",
            version=CommonCliParamsTests.default_version,
            release_license=CommonCliParamsTests.default_release_license,
            release_x_pack_components=CommonCliParamsTests.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        self.assertTrue(common_cli_params.is_nightly)
        self.assertFalse(common_cli_params.is_release)
        self.assertFalse(common_cli_params.is_adhoc)
        self.assertFalse(common_cli_params.is_docker)
        self.assertFalse(common_cli_params.release_params)

        self.assertEqual("bare", common_cli_params.setup)
        self.assertEqual("nightly", common_cli_params.configuration_name)
        self.assertEqual("master", common_cli_params.version)
        self.assertFalse(common_cli_params.release_params)
        self.assertEqual(os.path.basename(race_configs_id), common_cli_params.race_configs_id)

    def test_parses_release_6_6_0(self):
        race_configs_id = get_random_race_configs_id()

        common_cli_params = night_rally.CommonCliParams(
            mode="release",
            configuration_name="release",
            version="6.6.0",
            release_license=CommonCliParamsTests.default_release_license,
            release_x_pack_components=CommonCliParamsTests.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        self.assertFalse(common_cli_params.is_nightly)
        self.assertTrue(common_cli_params.is_release)
        self.assertFalse(common_cli_params.is_adhoc)
        self.assertFalse(common_cli_params.is_docker)

        self.assertTrue(common_cli_params.release_params)
        self.assertEqual("bare-oss", common_cli_params.setup)
        self.assertEqual("release", common_cli_params.configuration_name)
        self.assertEqual("6.6.0", common_cli_params.version)
        self.assertEqual({"license": "oss"}, common_cli_params.release_params)
        self.assertEqual(os.path.basename(race_configs_id), common_cli_params.race_configs_id)

    def test_parses_release_with_security_6_5_3(self):
        race_configs_id = get_random_race_configs_id()

        common_cli_params = night_rally.CommonCliParams(
            mode="release:x-pack",
            configuration_name="release",
            version="6.5.3",
            release_license="trial",
            release_x_pack_components="security",
            race_configs_id=race_configs_id
        )

        self.assertFalse(common_cli_params.is_nightly)
        self.assertTrue(common_cli_params.is_release)
        self.assertFalse(common_cli_params.is_adhoc)
        self.assertFalse(common_cli_params.is_docker)

        self.assertTrue(common_cli_params.release_params)
        self.assertEqual("bare-trial-security", common_cli_params.setup)
        self.assertEqual("release", common_cli_params.configuration_name)
        self.assertEqual("6.5.3", common_cli_params.version)
        self.assertEqual({"license": "trial", "x-pack-components": ["security"]}, common_cli_params.release_params)
        self.assertEqual(os.path.basename(race_configs_id), common_cli_params.race_configs_id)

    def test_parses_release_with_security_and_monitoring_6_5_1(self):
        race_configs_id = get_random_race_configs_id()

        common_cli_params = night_rally.CommonCliParams(
            mode="release:x-pack",
            configuration_name="release",
            version="6.5.1",
            release_license="trial",
            release_x_pack_components="security,monitoring",
            race_configs_id=race_configs_id
        )

        self.assertFalse(common_cli_params.is_nightly)
        self.assertTrue(common_cli_params.is_release)
        self.assertFalse(common_cli_params.is_adhoc)
        self.assertFalse(common_cli_params.is_docker)

        self.assertTrue(common_cli_params.release_params)
        # TODO: be specific about additional plugins
        self.assertEqual("bare-trial-security", common_cli_params.setup)
        self.assertEqual("release", common_cli_params.configuration_name)
        self.assertEqual("6.5.1", common_cli_params.version)
        self.assertEqual({
            "license": "trial",
            "x-pack-components": ["security","monitoring"]},
            common_cli_params.release_params
        )
        self.assertEqual(os.path.basename(race_configs_id), common_cli_params.race_configs_id)

    def test_parses_release_ear_6_2_1(self):
        race_configs_id = get_random_race_configs_id()

        common_cli_params = night_rally.CommonCliParams(
            mode="release:encryption-at-rest",
            configuration_name="release",
            version="6.2.1",
            release_license="oss",
            release_x_pack_components=CommonCliParamsTests.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        self.assertFalse(common_cli_params.is_nightly)
        self.assertTrue(common_cli_params.is_release)
        self.assertFalse(common_cli_params.is_adhoc)
        self.assertFalse(common_cli_params.is_docker)

        self.assertTrue(common_cli_params.release_params)
        self.assertEqual("ear-oss", common_cli_params.setup)
        self.assertEqual("release", common_cli_params.configuration_name)
        self.assertEqual("6.2.1", common_cli_params.version)
        self.assertEqual({
            "license": "oss"
            },
            common_cli_params.release_params
        )
        self.assertEqual(os.path.basename(race_configs_id), common_cli_params.race_configs_id)

    def test_parses_docker_release_6_2_2(self):
        race_configs_id = get_random_race_configs_id()

        common_cli_params = night_rally.CommonCliParams(
            mode="release:docker",
            configuration_name="release",
            version="6.2.2",
            release_license="oss",
            release_x_pack_components=CommonCliParamsTests.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        self.assertFalse(common_cli_params.is_nightly)
        self.assertTrue(common_cli_params.is_release)
        self.assertFalse(common_cli_params.is_adhoc)
        self.assertTrue(common_cli_params.is_docker)

        self.assertTrue(common_cli_params.release_params)
        self.assertEqual("docker-oss", common_cli_params.setup)
        self.assertEqual("release", common_cli_params.configuration_name)
        self.assertEqual("6.2.2", common_cli_params.version)
        self.assertTrue({
            "license": "oss"
            },
            common_cli_params.release_params
        )
        self.assertEqual(os.path.basename(race_configs_id), common_cli_params.race_configs_id)

    def test_docker_and_x_pack_raises_runtime_error(self):
        with self.assertRaises(RuntimeError) as ctx:
            night_rally.CommonCliParams(
                mode="release:docker",
                configuration_name="release",
                version="6.2.2",
                release_license="oss",
                release_x_pack_components="security",
                race_configs_id=os.path.basename(get_random_race_configs_id())
            )
        self.assertEqual(
            "User specified x-pack configuration [security] but this is not supported for Docker benchmarks.",
            ctx.exception.args[0]
        )

    def test_parses_adhoc_benchmarks(self):
        race_configs_id = get_random_race_configs_id()

        common_cli_params = night_rally.CommonCliParams(
            mode="adhoc",
            configuration_name="adhoc",
            version="lucene-7",
            release_license="oss",
            release_x_pack_components=CommonCliParamsTests.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        self.assertFalse(common_cli_params.is_nightly)
        self.assertFalse(common_cli_params.is_release)
        self.assertTrue(common_cli_params.is_adhoc)
        self.assertFalse(common_cli_params.is_docker)

        self.assertFalse(common_cli_params.release_params)
        self.assertEqual("bare", common_cli_params.setup)
        self.assertEqual("adhoc", common_cli_params.configuration_name)
        self.assertEqual("lucene-7", common_cli_params.version)
        self.assertFalse(common_cli_params.release_params)
        self.assertEqual(os.path.basename(race_configs_id), common_cli_params.race_configs_id)


class NightRallyTests(unittest.TestCase):
    def test_sanitize(self):
        self.assertEqual("lucene-7-upgrade", night_rally.sanitize("Lucene 7 Upgrade"))
        self.assertEqual("lucene-7-upgrade", night_rally.sanitize("lucene-7-upgrade"))
        self.assertEqual("elasticsearch-6_0_0-alpha1-docker", night_rally.sanitize("Elasticsearch 6.0.0-alpha1 Docker"))

    def test_join(self):
        self.assertEqual("env:bare,name:test", night_rally.join_nullables("env:bare", None, "name:test"))
        self.assertEqual("name:test", night_rally.join_nullables(None, "name:test"))
        self.assertEqual("", night_rally.join_nullables(None))

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_two_oss_challenges_successfully(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "geonames-append-1node",
                                        "label": "add-defaults",
                                        "charts": [
                                            "indexing",
                                            "query",
                                            "gc",
                                            "io"
                                        ],
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults"
                                    },
                                    {
                                        "name": "geonames-append-4g-1node",
                                        "label": "add-4g",
                                        "charts": [
                                            "indexing"
                                        ],
                                        "challenge": "append-no-conflicts-index-only",
                                        "track-params": {
                                            "number_of_replicas": 0
                                        },
                                        "car": "4gheap"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 1, 1)
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("nightly", start_date, 8, "bare", race_configs_id=race_configs_id)]
        cmd = night_rally.NightlyCommand(params, start_date)
        night_rally.run_rally(tracks, None, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"defaults\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-append-1node,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-complete\" "
                "--revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id),

                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts-index-only\" --car=\"4gheap\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-append-4g-1node,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
                "--track-params=\"{{\\\"number_of_replicas\\\": 0}}\" --pipeline=\"from-sources-skip-build\" "
                "--revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id)
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_two_mixed_license_challenges_successfully(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
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
                    },
                    {
                        "name": "default",
                        "licenses": [
                            {
                                "name": "basic",
                                "configurations": [
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
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 1, 1)
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("nightly", start_date, 8, "bare", race_configs_id=race_configs_id)]
        cmd = night_rally.NightlyCommand(params, start_date)
        night_rally.run_rally(tracks, None, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(4, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"defaults\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-defaults,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-complete\" "
                "--revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id),

                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"4gheap\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-4g,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-skip-build\" --revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id),

                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"defaults,basic-license\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-defaults,setup:bare,race-configs-id:{},license:basic\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-complete\" --revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id),

                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"4gheap,basic-license\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-4g,setup:bare,race-configs-id:{},license:basic\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-skip-build\" --revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id)
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_two_oss_tracks_successfully(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "track": "percolator",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "percolator-4g",
                                        "challenge": "append-no-conflicts",
                                        "car": "4gheap"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 10, 1)
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("nightly", start_date, 8, "bare", race_configs_id=race_configs_id)]
        cmd = night_rally.NightlyCommand(params, start_date)
        night_rally.run_rally(tracks, None, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"defaults\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-defaults,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-complete\" --revision=\"@2016-10-01T00:00:00Z\"".format(race_configs_id),

                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"percolator\" "
                "--challenge=\"append-no-conflicts\" --car=\"4gheap\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:percolator-4g,setup:bare,race-configs-id:{},license:oss\" "
                "--runtime-jdk=\"8\" --pipeline=\"from-sources-skip-build\" "
                "--revision=\"@2016-10-01T00:00:00Z\"".format(race_configs_id)
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_three_sets_of_mixed_license_tracks_successfully(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)
        self.maxDiff = None
        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults"
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "name": "default",
                        "licenses": [
                            {
                                "name": "basic",
                                "configurations": [
                                    {
                                        "name": "geonames-append-4g-3nodes",
                                        "challenge": "append-no-conflicts",
                                        "car": "4gheap"
                                    }
                                ]
                            },
                            {
                                "name": "trial",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults"
                                    },
                                    {
                                        "name": "geonames-append-defaults-x-pack-security-1node",
                                        "label": "add-defaults-security",
                                        "charts": ["indexing"],
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults",
                                        "car-params": {
                                            "xpack_ml_enabled": False,
                                            "xpack_monitoring_enabled": False,
                                            "xpack_watcher_enabled": False
                                        },
                                        "track-params": {
                                            "number_of_replicas": 0
                                        },
                                        "x-pack": ["security"]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "track": "percolator",
                "flavors": [
                    {
                        "name": "default",
                        "licenses": [
                            {
                                "name": "trial",
                                "configurations": [
                                    {
                                        "name": "percolator-4g",
                                        "challenge": "append-no-conflicts",
                                        "car": "4gheap",
                                        "car-params": {
                                            "xpack_ml_enabled": False,
                                            "xpack_monitoring_enabled": False,
                                            "xpack_watcher_enabled": False
                                        },
                                        "x-pack": ["security"]
                                    },
                                    {
                                        "name": "percolator",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults",
                                        "car-params": {
                                            "xpack_ml_enabled": False,
                                            "xpack_monitoring_enabled": False,
                                            "xpack_watcher_enabled": False
                                        },
                                        "x-pack": ["security"]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 10, 1)
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("nightly", start_date, 8, "bare", race_configs_id=race_configs_id)]
        cmd = night_rally.NightlyCommand(params, start_date)
        night_rally.run_rally(tracks, None, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(6, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"defaults\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-defaults,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-complete\" --revision=\"@2016-10-01T00:00:00Z\"".format(race_configs_id),

                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"4gheap,basic-license\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-append-4g-3nodes,setup:bare,race-configs-id:{},license:basic\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-complete\" --revision=\"@2016-10-01T00:00:00Z\"".format(race_configs_id),

                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"defaults,trial-license\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-defaults,setup:bare,race-configs-id:{},license:trial\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-complete\" --revision=\"@2016-10-01T00:00:00Z\"".format(race_configs_id),

                'rally --skip-update --configuration-name="nightly" --quiet '
                '--target-host="localhost:39200" --effective-start-date="2016-10-01 00:00:00" '
                '--track-repository="default" --track="geonames" --challenge="append-no-conflicts" '
                '--car="defaults,trial-license,x-pack-security" '
                '--client-options="timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:\'rally\''
                ',basic_auth_password:\'rally-password\'" '
                '--user-tag="name:geonames-append-defaults-x-pack-security-1node,setup:bare,race-configs-id:{},license:trial,x-pack:true" '
                '--runtime-jdk="8" --car-params="{{\\"xpack_ml_enabled\\": false, '
                '\\"xpack_monitoring_enabled\\": false, \\"xpack_watcher_enabled\\": false}}" '
                '--track-params="{{\\"number_of_replicas\\": 0}}" '
                # recompile as license has changed
                '--pipeline="from-sources-complete" --revision="@2016-10-01T00:00:00Z"'.format(race_configs_id),

                'rally --skip-update --configuration-name="nightly" --quiet '
                '--target-host="localhost:39200" --effective-start-date="2016-10-01 00:00:00" '
                '--track-repository="default" --track="percolator" --challenge="append-no-conflicts" '
                '--car="4gheap,trial-license,x-pack-security" '
                '--client-options="timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:\'rally\''
                ',basic_auth_password:\'rally-password\'" '
                '--user-tag="name:percolator-4g,setup:bare,race-configs-id:{},license:trial,x-pack:true" --runtime-jdk="8" '
                '--car-params="{{\\"xpack_ml_enabled\\": false, \\"xpack_monitoring_enabled\\": false, '
                '\\"xpack_watcher_enabled\\": false}}" --pipeline="from-sources-skip-build" '
                '--revision="@2016-10-01T00:00:00Z"'.format(race_configs_id),

                'rally --skip-update --configuration-name="nightly" --quiet '
                '--target-host="localhost:39200" --effective-start-date="2016-10-01 00:00:00" '
                '--track-repository="default" --track="percolator" --challenge="append-no-conflicts" '
                '--car="defaults,trial-license,x-pack-security" '
                '--client-options="timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:\'rally\''
                ',basic_auth_password:\'rally-password\'" '
                '--user-tag="name:percolator,setup:bare,race-configs-id:{},license:trial,x-pack:true" --runtime-jdk="8" '
                '--car-params="{{\\"xpack_ml_enabled\\": false, \\"xpack_monitoring_enabled\\": false, '
                '\\"xpack_watcher_enabled\\": false}}" --pipeline="from-sources-skip-build" '
                '--revision="@2016-10-01T00:00:00Z"'.format(race_configs_id)
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_adhoc_benchmark(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)
        self.maxDiff = None
        tracks = [
            {
                "track-repository": "eventdata",
                "track": "eventdata",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "eventdata-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "track": "percolator",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "percolator-4g",
                                        "challenge": "append-no-conflicts",
                                        "car": "4gheap"
                                    }
                                ]

                            }
                        ]
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 10, 1)
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("lucene-7", start_date, 8, "bare", race_configs_id=race_configs_id)]
        cmd = night_rally.AdHocCommand(params, "66202dc")

        night_rally.run_rally(tracks, None, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"lucene-7\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"eventdata\" --track=\"eventdata\" "
                "--challenge=\"append-no-conflicts\" --car=\"defaults\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:eventdata-defaults,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-complete\" --revision=\"66202dc\"".format(race_configs_id),

                "rally --skip-update --configuration-name=\"lucene-7\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"percolator\" "
                "--challenge=\"append-no-conflicts\" --car=\"4gheap\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:percolator-4g,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-skip-build\" --revision=\"66202dc\"".format(race_configs_id)
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_release_benchmark_without_plugins(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
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
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 1, 1)
        release_params= OrderedDict({"license": "oss"})
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "bare-oss", race_configs_id=race_configs_id)]
        cmd = night_rally.ReleaseCommand(params, release_params, "5.3.0")
        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"defaults\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-defaults,setup:bare-oss,race-configs-id:{},license:oss\" "
                "--runtime-jdk=\"8\" --distribution-version=\"5.3.0\" "
                "--pipeline=\"from-distribution\"".format(race_configs_id),

                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"4gheap\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-4g,setup:bare-oss,race-configs-id:{},license:oss\" "
                "--runtime-jdk=\"8\" --distribution-version=\"5.3.0\" "
                "--pipeline=\"from-distribution\"".format(race_configs_id)
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_release_benchmark_with_plugins(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            # skip, since we are in release mode, forcing trial license
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults",
                                        "track-params": "bulk_size:3000"
                                    },
                                    {
                                        "name": "geonames-4g",
                                        "challenge": "append-no-conflicts",
                                        "car": "4gheap",
                                        "track-params": "bulk_size:2000"
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "name": "default",
                        "licenses": [
                            {
                                "name": "basic",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults",
                                        "track-params": "bulk_size:3000"
                                    },
                                    {
                                        "name": "geonames-4g",
                                        "challenge": "append-no-conflicts",
                                        "car": "4gheap",
                                        "track-params": "bulk_size:2000"
                                    }
                                ]
                            },
                            {
                                "name": "trial",
                                "configurations": [
                                    # should not run this combination - because we filter x-pack configs
                                    {
                                        "name": "geonames-4g-with-x-pack",
                                        "challenge": "append-no-conflicts",
                                        "car": "4gheap",
                                        "x-pack": ["security"],
                                        "track-params": "bulk_size:1000"
                                    },
                                    # should run an ML benchmark
                                    {
                                        "name": "geonames-4g-with-ml",
                                        "challenge": "append-ml",
                                        "car": "4gheap",
                                        "x-pack": ["ml"]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 1, 1)
        race_configs_id = os.path.basename(get_random_race_configs_id())
        release_params = OrderedDict({"license": "trial", "x-pack-components": ["security", "monitoring"]})
        params = [night_rally.StandardParams("release", start_date, 8, "bare-trial-security", race_configs_id=race_configs_id)]
        cmd = night_rally.ReleaseCommand(params, release_params, "5.4.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(3, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"defaults\" "
                "--client-options=\"timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:'rally',"
                "basic_auth_password:'rally-password'\" "
                "--user-tag=\"name:geonames-defaults,setup:bare-trial-security,race-configs-id:{},license:trial,x-pack:true,"
                "x-pack-components:security,monitoring\" "
                "--runtime-jdk=\"8\" --track-params=\"bulk_size:3000\" "
                "--elasticsearch-plugins=\"x-pack:security+monitoring\" "
                "--distribution-version=\"5.4.0\" --pipeline=\"from-distribution\"".format(race_configs_id),

                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"4gheap\" "
                "--client-options=\"timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:'rally',"
                "basic_auth_password:'rally-password'\" "
                "--user-tag=\"name:geonames-4g,setup:bare-trial-security,race-configs-id:{},license:trial,x-pack:true,"
                "x-pack-components:security,monitoring\" "
                "--runtime-jdk=\"8\" --track-params=\"bulk_size:2000\" "
                "--elasticsearch-plugins=\"x-pack:security+monitoring\" --distribution-version=\"5.4.0\" "
                "--pipeline=\"from-distribution\"".format(race_configs_id),

                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-ml\" --car=\"4gheap\" "
                "--client-options=\"timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:'rally',"
                "basic_auth_password:'rally-password'\" "
                "--user-tag=\"name:geonames-4g-with-ml,setup:bare-trial-security,race-configs-id:{},license:trial,x-pack:true"
                ",x-pack-components:security,monitoring\" "
                "--runtime-jdk=\"8\""
                " --elasticsearch-plugins=\"x-pack:ml+security+monitoring\" "
                "--distribution-version=\"5.4.0\" --pipeline=\"from-distribution\"".format(race_configs_id),
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_trial_release_benchmarks_with_x_pack_module(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "default",
                        "licenses": [
                            {
                                "name": "basic",
                                "configurations": [
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
                            },
                            {
                                "name": "trial",
                                "configurations": [
                                    # should not run this combination - because we filter x-pack configs
                                    {
                                        "name": "geonames-4g-with-x-pack",
                                        "challenge": "append-no-conflicts",
                                        "car": "4gheap",
                                        "x-pack": "security"
                                    }
                                ]

                            }
                        ]
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 1, 1)
        release_params = OrderedDict({"license": "trial", "x-pack-components": ["security"]})
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "bare-trial-security", race_configs_id=race_configs_id)]
        # 6.3.0 is the first version to include x-pack as a module
        cmd = night_rally.ReleaseCommand(params, release_params, "6.3.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            ['rally --skip-update --configuration-name="release" --quiet '
             '--target-host="localhost:39200" --effective-start-date="2016-01-01 00:00:00" '
             '--track-repository="default" --track="geonames" --challenge="append-no-conflicts" '
             '--car="defaults,trial-license,x-pack-security" '
             '--client-options="timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:\'rally\''
             ',basic_auth_password:\'rally-password\'" '
             "--user-tag=\"name:geonames-defaults,setup:bare-trial-security,race-configs-id:{},license:trial,"
             "x-pack:true,x-pack-components:security\" "
             '--runtime-jdk="8" --distribution-version="6.3.0" '
             '--pipeline="from-distribution"'.format(race_configs_id),

             'rally --skip-update --configuration-name="release" --quiet '
             '--target-host="localhost:39200" --effective-start-date="2016-01-01 00:00:00" '
             '--track-repository="default" --track="geonames" --challenge="append-no-conflicts" '
             '--car="4gheap,trial-license,x-pack-security" '
             '--client-options="timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:\'rally\''
             ',basic_auth_password:\'rally-password\'" '
             "--user-tag=\"name:geonames-4g,setup:bare-trial-security,race-configs-id:{},license:trial,"
             "x-pack:true,x-pack-components:security\" "
             '--runtime-jdk="8" --distribution-version="6.3.0" '
             '--pipeline="from-distribution"'.format(race_configs_id)]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_release_benchmark_with_basic_license(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)
        self.maxDiff = None

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        # skip this
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults"
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "name": "default",
                        "licenses": [
                            {
                                "name": "basic",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 1, 1)
        release_params = OrderedDict({"license": "basic"})
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "bare-basic", race_configs_id=race_configs_id)]
        cmd = night_rally.ReleaseCommand(params, release_params, distribution_version="7.0.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(1, len(system_call.calls))
        self.assertEqual(
            [
                'rally --skip-update --configuration-name="release" --quiet '
                '--target-host="localhost:39200" --effective-start-date="2016-01-01 00:00:00" '
                '--track-repository="default" --track="geonames" --challenge="append-no-conflicts" '
                '--car="defaults,basic-license" '
                '--client-options="timeout:240" '
                '--user-tag="name:geonames-defaults,setup:bare-basic,race-configs-id:{},license:basic" '
                '--runtime-jdk="8" '
                '--distribution-version="7.0.0" --pipeline="from-distribution"'.format(race_configs_id)
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_release_benchmark_with_transport_nio(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)
        self.maxDiff = None

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": ["defaults", "unpooled"],
                                        "plugins": "transport-nio:transport+http"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 1, 1)
        release_params = OrderedDict({"license": "oss"})
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "bare-oss",race_configs_id=race_configs_id)]
        cmd = night_rally.ReleaseCommand(params, release_params, distribution_version="7.0.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(1, len(system_call.calls))
        self.assertEqual(
            [
                'rally --skip-update --configuration-name="release" --quiet '
                '--target-host="localhost:39200" --effective-start-date="2016-01-01 00:00:00" '
                '--track-repository="default" --track="geonames" --challenge="append-no-conflicts" '
                '--car="defaults,unpooled" '
                '--client-options="timeout:240" '
                '--user-tag="name:geonames-defaults,setup:bare-oss,race-configs-id:{},license:oss" '
                '--runtime-jdk="8" --elasticsearch-plugins="transport-nio:transport+http" '
                '--distribution-version="7.0.0" --pipeline="from-distribution"'.format(race_configs_id)
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_do_not_run_release_benchmark_with_transport_nio_and_x_pack(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults",
                                        "plugins": "transport-nio:transport+http"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 1, 1)
        race_configs_id = os.path.basename(get_random_race_configs_id())
        release_params = {"license": "trial", "x-pack-components": ["security"]}
        params = [night_rally.StandardParams("release", start_date, 8, "bare-trial-security", race_configs_id=race_configs_id)]
        cmd = night_rally.ReleaseCommand(params, release_params, "7.0.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(0, len(system_call.calls))

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_do_not_run_oss_license_release_benchmark_with_x_pack_components_other_than_monitoring(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "nyc_taxis",
                "flavors": [
                    {
                        "name": "default",
                        "licenses": [
                            {
                                "name": "trial",
                                "configurations": [
                                {
                                    "name": "nyc_taxis-ml-4g-1node",
                                    "label": "ml-4g",
                                    "#COMMENT": "Don't generate any standard charts but we'll create ML-specific charts",
                                    "charts": [],
                                    "challenge": "append-ml",
                                    "car": "4gheap",
                                    "x-pack": [
                                        "ml"
                                    ]
                                }
                            ]
                            }
                        ]
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 1, 1)
        release_params = {"license": "oss", "x-pack-components": ["ml"]}
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "bare-oss", race_configs_id=race_configs_id)]
        cmd = night_rally.ReleaseCommand(params, release_params, "7.0.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(0, len(system_call.calls))

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_do_not_run_release_benchmark_with_transport_nio_on_old_version(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults",
                                        "plugins": "transport-nio:transport+http"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        release_params = {"license": "oss"}
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "bare-oss", race_configs_id=race_configs_id)]
        # 6.2.0 does not have transport-nio available
        cmd = night_rally.ReleaseCommand(params, release_params, distribution_version="6.2.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(0, len(system_call.calls))

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_docker_5x_benchmark(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)
        self.maxDiff = None
        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
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
                    }
                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        release_params = OrderedDict({"license": "oss"})
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "docker-oss", race_configs_id=race_configs_id)]
        cmd = night_rally.DockerCommand(params, release_params, "5.6.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                'rally --skip-update --configuration-name="release" --quiet --target-host="localhost:39200" '
                '--effective-start-date="2016-01-01 00:00:00" --track-repository=\"default\" --track="geonames" '
                '--challenge="append-no-conflicts" --car="defaults" --client-options="timeout:240" '
                "--user-tag=\"name:geonames-defaults,setup:docker-oss,race-configs-id:{},license:oss\" "
                '--runtime-jdk="8" --distribution-version="5.6.0" '
                '--pipeline="docker" --car-params="{{\\"additional_cluster_settings\\": '
                '{{\\"xpack.security.enabled\\": \\"false\\", \\"xpack.ml.enabled\\": \\"false\\", '
                '\\"xpack.monitoring.enabled\\": \\"false\\", \\"xpack.watcher.enabled\\": \\"false\\"}}}}"'.format(race_configs_id),

                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"4gheap\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-4g,setup:docker-oss,race-configs-id:{},license:oss\" "
                "--runtime-jdk=\"8\" --distribution-version=\"5.6.0\" "
                "--pipeline=\"docker\" --car-params=\"{{\\\"additional_cluster_settings\\\": "
                "{{\\\"xpack.security.enabled\\\": \\\"false\\\", \\\"xpack.ml.enabled\\\": \\\"false\\\", "
                "\\\"xpack.monitoring.enabled\\\": \\\"false\\\", "
                "\\\"xpack.watcher.enabled\\\": \\\"false\\\"}}}}\"".format(race_configs_id),
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_docker_6x_benchmark(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
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
                    }
                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        release_params = OrderedDict({"license": "oss"})
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "docker-oss", race_configs_id=race_configs_id)]
        cmd = night_rally.DockerCommand(params, release_params, "6.3.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"defaults\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-defaults,setup:docker-oss,race-configs-id:{},license:oss\" "
                "--runtime-jdk=\"8\" --distribution-version=\"6.3.0\" "
                "--pipeline=\"docker\"".format(race_configs_id),

                "rally --skip-update --configuration-name=\"release\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"4gheap\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-4g,setup:docker-oss,race-configs-id:{},license:oss\" "
                "--runtime-jdk=\"8\" --distribution-version=\"6.3.0\" "
                "--pipeline=\"docker\"".format(race_configs_id)
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_skip_any_plugins_with_docker(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults",
                                        "plugins": "transport-nio:transport+http",
                                    },
                                    {
                                        "name": "geonames-4g",
                                        "challenge": "append-no-conflicts",
                                        "car": "4gheap",
                                        "plugins": "transport-nio:transport+http",
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        release_params = OrderedDict({"license": "oss"})
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "docker-oss", race_configs_id=race_configs_id)]
        cmd = night_rally.DockerCommand(params, release_params, "7.3.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(0, len(system_call.calls))

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_continues_on_error(self, mocked_wait_until_port_is_free):
        self.maxDiff = None
        system_call = RecordingSystemCall(return_value=True)

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "track": "percolator",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "percolator-4g",
                                        "challenge": "append-no-conflicts",
                                        "car": "4gheap"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        start_date = datetime.datetime(2016, 10, 1)
        params = [night_rally.StandardParams("nightly", start_date, 8, "bare")]
        cmd = night_rally.NightlyCommand(params, start_date)
        night_rally.run_rally(tracks, None, ["localhost"], cmd, skip_ansible=True, system=system_call)

        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"defaults\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-defaults,setup:bare,license:oss\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-complete\" --revision=\"@2016-10-01T00:00:00Z\"",

                "rally --skip-update --configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"percolator\" "
                "--challenge=\"append-no-conflicts\" --car=\"4gheap\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:percolator-4g,setup:bare,license:oss\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-skip-build\" --revision=\"@2016-10-01T00:00:00Z\""
            ]
            ,
            system_call.calls
        )

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_with_telemetry(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)
        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "oss",
                        "licenses": [
                            {
                                "name": "oss",
                                "configurations": [
                                    {
                                        "name": "geonames-defaults",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults"
                                    }
                                ]
                            }
                        ]
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
            night_rally.StandardParams("nightly", start_date, 8, "bare")]

        cmd = night_rally.NightlyCommand(params, start_date)

        night_rally.run_rally(tracks, None, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(1, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --telemetry=\"jfr,gc,jit\" --telemetry-params=\"recording-template:profile\" "
                "--configuration-name=\"nightly\" --quiet --target-host=\"localhost:39200\" "
                "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
                "--challenge=\"append-no-conflicts\" --car=\"defaults\" --client-options=\"timeout:240\" "
                "--user-tag=\"name:geonames-defaults,setup:bare,license:oss\" --runtime-jdk=\"8\" "
                "--pipeline=\"from-sources-complete\" --revision=\"@2016-01-01T00:00:00Z\""
            ]
            ,
            system_call.calls
        )
