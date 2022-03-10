import datetime
import os

from collections import OrderedDict
from unittest import mock
from night_rally import night_rally
from night_rally.night_rally import TelemetryParams, csv_to_list
from . import get_random_race_configs_id
import pytest


class RecordingSystemCall:
    def __init__(self, return_value):
        self.calls = []
        self.return_value = return_value

    def __call__(self, *args, **kwargs):
        self.calls.append(*args)
        return self.return_value


class TestVersions():
    def test_finds_components_for_valid_version(self):
        assert night_rally.components("5.0.3") == (5, 0, 3, None) 
        assert night_rally.components("5.0.3-SNAPSHOT") == (5, 0, 3, "SNAPSHOT") 

    def test_components_ignores_invalid_versions(self):
        with pytest.raises(ValueError) as exc:
            night_rally.components("5.0.0a")
        assert exc.value.args[0] == r"version string '5.0.0a' does not conform to pattern '^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$'" 


class TestSkipTrack():
    def test_allows_dense_vector_with_es_8(self):
        assert night_rally.run_track("dense_vector", 8), "dense_vector shouldn't run if ES is <8"
        
    def test_allows_geopointshape_with_es_7(self):
        assert night_rally.run_track("geopointshape", 7), "geopointshape shouldn't run if ES is <7"

    def test_fails_eql_with_es_6(self):
        assert not night_rally.run_track("eql", 6), "eql shouldn't run if ES is <7"

    def test_always_run_tracks_not_in_blacklist(self):
        assert night_rally.run_track("somenewtrack", 5), "allow non blacklisted track to run with any ES version"


class TestNightRally():
    def test_sanitize(self):
        assert night_rally.sanitize("Lucene 7 Upgrade") == "lucene-7-upgrade"
        assert night_rally.sanitize("lucene-7-upgrade") == "lucene-7-upgrade"
        assert night_rally.sanitize("Elasticsearch 6.0.0-alpha1 Docker") == "elasticsearch-6_0_0-alpha1-docker"

    def test_join(self):
        assert night_rally.join_nullables("env:bare", None, "name:test") == "env:bare,name:test"
        assert night_rally.join_nullables(None, "name:test") == "name:test"
        assert night_rally.join_nullables(None) == ""

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_mix_telemetry_from_command_line_and_race_config(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "flavors": [
                    {
                        "name": "default",
                        "licenses": [
                            {
                                "name": "trial",
                                "configurations": [
                                    {
                                        "name": "geonames-append-1node",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults",
                                        "telemetry": ["gc"]
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

        # passing --telemetry as a cli arg in night rally
        params = [TelemetryParams(csv_to_list("node-stats"), csv_to_list("node-stats-sample-interval:1")),
                  night_rally.StandardParams("nightly", start_date, 8, "bare", race_configs_id=race_configs_id)]

        cmd = night_rally.NightlyCommand(params, start_date)
        night_rally.run_rally(tracks, None, ["localhost"], cmd, skip_ansible=True, system=system_call)
        assert len(system_call.calls) == 1
        assert system_call.calls == [
            "rally --skip-update race --telemetry=\"node-stats,gc\" "
            "--telemetry-params=\"node-stats-sample-interval:1\" "
            "--configuration-name=\"nightly\" --quiet "
            "--target-host=\"localhost:9200\" --effective-start-date=\"2016-01-01 00:00:00\" "
            "--track-repository=\"default\" --track=\"geonames\" --challenge=\"append-no-conflicts\" "
            "--car=\"defaults,trial-license\" --on-error=\"abort\" --client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-append-1node,setup:bare,race-configs-id:{},license:trial\" --runtime-jdk=\"8\" "
            "--pipeline=\"from-sources\" "
            "--revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id),
        ]

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
        assert len(system_call.calls) == 2
        assert system_call.calls == [
            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults\" --on-error=\"abort\" --client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-append-1node,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
            "--pipeline=\"from-sources\" "
            "--revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id),

            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts-index-only\" --car=\"4gheap\" --on-error=\"abort\" "
            "--client-options=\"timeout:240\" --user-tag=\"name:geonames-append-4g-1node,setup:bare,race-configs-id:{},license:oss\" "
            "--runtime-jdk=\"8\" --track-params=\"{{\\\"number_of_replicas\\\": 0}}\" --pipeline=\"from-sources\" "
            "--revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id)
        ]
        
    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_exclude_tasks_option(self, mocked_wait_until_port_is_free):
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
                                        "name": "geonames-append-1node",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults",
                                        "exclude-tasks": "delete,type:search"
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
        assert system_call.calls == [
            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults,basic-license\" --on-error=\"abort\" --client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-append-1node,setup:bare,race-configs-id:{},license:basic\" --runtime-jdk=\"8\" "
            "--exclude-tasks=\"delete,type:search\" --pipeline=\"from-sources\" "
            "--revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id)
        ]

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_overwrite_runtime_jdk_successfully(self, mocked_wait_until_port_is_free):
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
                                        "name": "geonames-append-1node",
                                        "challenge": "append-no-conflicts",
                                        "car": "defaults",
                                        "runtime-jdk": "13"
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
        assert system_call.calls == [
            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults,basic-license\" --on-error=\"abort\" --client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-append-1node,setup:bare,race-configs-id:{},license:basic\" --runtime-jdk=\"13\" "
            "--pipeline=\"from-sources\" "
            "--revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id)
        ]

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
        assert len(system_call.calls) == 4
        assert system_call.calls == [
            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults\" --on-error=\"abort\" --client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-defaults,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
            "--pipeline=\"from-sources\" "
            "--revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id),

            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"4gheap\" --on-error=\"abort\" --client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-4g,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
            "--pipeline=\"from-sources\" --revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id),

            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults,basic-license\" --on-error=\"abort\" "
            "--client-options=\"timeout:240\" --user-tag=\"name:geonames-defaults,setup:bare,race-configs-id:{},license:basic\" "
            "--runtime-jdk=\"8\" --pipeline=\"from-sources\" --revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id),

            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"4gheap,basic-license\" --on-error=\"abort\" "
            "--client-options=\"timeout:240\" --user-tag=\"name:geonames-4g,setup:bare,race-configs-id:{},license:basic\" "
            "--runtime-jdk=\"8\" --pipeline=\"from-sources\" --revision=\"@2016-01-01T00:00:00Z\"".format(race_configs_id)
        ]

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_two_oss_tracks_successfully(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)

        tracks = [
            {
                "track": "geonames",
                "placement": 0,
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
                "placement": 1,
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
        night_rally.run_rally(tracks, None, ["127.0.0.1", "127.0.0.2", "127.0.0.3"], cmd, skip_ansible=True, system=system_call)
        assert len(system_call.calls) == 2
        assert system_call.calls == [
            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"127.0.0.1:9200\" "
            "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults\" --on-error=\"abort\" --client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-defaults,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
            "--pipeline=\"from-sources\" --revision=\"@2016-10-01T00:00:00Z\"".format(race_configs_id),

            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"127.0.0.2:9200\" "
            "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"percolator\" "
            "--challenge=\"append-no-conflicts\" --car=\"4gheap\" --on-error=\"abort\" --client-options=\"timeout:240\" "
            "--user-tag=\"name:percolator-4g,setup:bare,race-configs-id:{},license:oss\" "
            "--runtime-jdk=\"8\" --pipeline=\"from-sources\" "
            "--revision=\"@2016-10-01T00:00:00Z\"".format(race_configs_id)
        ]

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
        assert len(system_call.calls) == 6
        assert system_call.calls == [
            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults\" --on-error=\"abort\" --client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-defaults,setup:bare,race-configs-id:{},license:oss\" --runtime-jdk=\"8\" "
            "--pipeline=\"from-sources\" --revision=\"@2016-10-01T00:00:00Z\"".format(race_configs_id),

            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"4gheap,basic-license\" --on-error=\"abort\" "
            "--client-options=\"timeout:240\" --user-tag=\"name:geonames-append-4g-3nodes,setup:bare,race-configs-id:{},license:basic\" "
            "--runtime-jdk=\"8\" --pipeline=\"from-sources\" --revision=\"@2016-10-01T00:00:00Z\"".format(race_configs_id),

            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults,trial-license\" --on-error=\"abort\" "
            "--client-options=\"timeout:240\" --user-tag=\"name:geonames-defaults,setup:bare,race-configs-id:{},license:trial\" "
            "--runtime-jdk=\"8\" --pipeline=\"from-sources\" --revision=\"@2016-10-01T00:00:00Z\"".format(race_configs_id),

            'rally --skip-update race --configuration-name="nightly" --quiet '
            '--target-host="localhost:9200" --effective-start-date="2016-10-01 00:00:00" '
            '--track-repository="default" --track="geonames" --challenge="append-no-conflicts" '
            '--car="defaults,trial-license,x-pack-security" --on-error="abort" '
            '--client-options="timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:\'rally\''
            ',basic_auth_password:\'rally-password\'" '
            '--user-tag="name:geonames-append-defaults-x-pack-security-1node,setup:bare,race-configs-id:{},license:trial,x-pack:true" '
            '--runtime-jdk="8" --car-params="{{\\"xpack_ml_enabled\\": false, '
            '\\"xpack_monitoring_enabled\\": false, \\"xpack_watcher_enabled\\": false}}" '
            '--track-params="{{\\"number_of_replicas\\": 0}}" '
            '--pipeline="from-sources" --revision="@2016-10-01T00:00:00Z"'.format(race_configs_id),

            'rally --skip-update race --configuration-name="nightly" --quiet '
            '--target-host="localhost:9200" --effective-start-date="2016-10-01 00:00:00" '
            '--track-repository="default" --track="percolator" --challenge="append-no-conflicts" '
            '--car="4gheap,trial-license,x-pack-security" --on-error="abort" '
            '--client-options="timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:\'rally\''
            ',basic_auth_password:\'rally-password\'" '
            '--user-tag="name:percolator-4g,setup:bare,race-configs-id:{},license:trial,x-pack:true" --runtime-jdk="8" '
            '--car-params="{{\\"xpack_ml_enabled\\": false, \\"xpack_monitoring_enabled\\": false, '
            '\\"xpack_watcher_enabled\\": false}}" --pipeline="from-sources" '
            '--revision="@2016-10-01T00:00:00Z"'.format(race_configs_id),

            'rally --skip-update race --configuration-name="nightly" --quiet '
            '--target-host="localhost:9200" --effective-start-date="2016-10-01 00:00:00" '
            '--track-repository="default" --track="percolator" --challenge="append-no-conflicts" '
            '--car="defaults,trial-license,x-pack-security" --on-error="abort" '
            '--client-options="timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:\'rally\''
            ',basic_auth_password:\'rally-password\'" '
            '--user-tag="name:percolator,setup:bare,race-configs-id:{},license:trial,x-pack:true" --runtime-jdk="8" '
            '--car-params="{{\\"xpack_ml_enabled\\": false, \\"xpack_monitoring_enabled\\": false, '
            '\\"xpack_watcher_enabled\\": false}}" --pipeline="from-sources" '
            '--revision="@2016-10-01T00:00:00Z"'.format(race_configs_id)
        ]

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_release_benchmark_without_plugins(self, mocked_wait_until_port_is_free):
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
        cmd = night_rally.ReleaseCommand(params, release_params, "5.3.0")
        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        assert len(system_call.calls) == 2
        assert system_call.calls == [
            "rally --skip-update race --configuration-name=\"release\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults\" --on-error=\"abort\" --client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-defaults,setup:bare-basic,race-configs-id:{},license:basic\" "
            "--runtime-jdk=\"8\" --distribution-version=\"5.3.0\" "
            "--pipeline=\"from-distribution\"".format(race_configs_id),

            "rally --skip-update race --configuration-name=\"release\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"4gheap\" --on-error=\"abort\" --client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-4g,setup:bare-basic,race-configs-id:{},license:basic\" "
            "--runtime-jdk=\"8\" --distribution-version=\"5.3.0\" "
            "--pipeline=\"from-distribution\"".format(race_configs_id)
        ]

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
                                    # should run an ML benchmark
                                    {
                                        "name": "geonames-4g-with-ml",
                                        "challenge": "append-ml",
                                        "car": "4gheap",
                                        "x-pack": ["ml", "security"]
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
        assert len(system_call.calls) == 3
        assert system_call.calls == [
            "rally --skip-update race --configuration-name=\"release\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults\" --on-error=\"abort\" "
            "--client-options=\"timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:'rally',"
            "basic_auth_password:'rally-password'\" "
            "--user-tag=\"name:geonames-defaults,setup:bare-trial-security,race-configs-id:{},license:trial,x-pack:true,"
            "x-pack-components:security,monitoring\" "
            "--runtime-jdk=\"8\" --track-params=\"bulk_size:3000\" "
            "--elasticsearch-plugins=\"x-pack:security+monitoring\" "
            "--distribution-version=\"5.4.0\" --pipeline=\"from-distribution\"".format(race_configs_id),

            "rally --skip-update race --configuration-name=\"release\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"4gheap\" --on-error=\"abort\" "
            "--client-options=\"timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:'rally',"
            "basic_auth_password:'rally-password'\" "
            "--user-tag=\"name:geonames-4g,setup:bare-trial-security,race-configs-id:{},license:trial,x-pack:true,"
            "x-pack-components:security,monitoring\" "
            "--runtime-jdk=\"8\" --track-params=\"bulk_size:2000\" "
            "--elasticsearch-plugins=\"x-pack:security+monitoring\" --distribution-version=\"5.4.0\" "
            "--pipeline=\"from-distribution\"".format(race_configs_id),

            "rally --skip-update race --configuration-name=\"release\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-ml\" --car=\"4gheap\" --on-error=\"abort\" "
            "--client-options=\"timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:'rally',"
            "basic_auth_password:'rally-password'\" "
            "--user-tag=\"name:geonames-4g-with-ml,setup:bare-trial-security,race-configs-id:{},license:trial,x-pack:true"
            ",x-pack-components:security,monitoring\" "
            "--runtime-jdk=\"8\""
            " --elasticsearch-plugins=\"x-pack:ml+security+monitoring\" "
            "--distribution-version=\"5.4.0\" --pipeline=\"from-distribution\"".format(race_configs_id),
        ]

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
                                        "x-pack": [
                                            "security"
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
        release_params = OrderedDict({"license": "trial", "x-pack-components": ["security"]})
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "bare-trial-security", race_configs_id=race_configs_id)]
        # 6.3.0 is the first version to include x-pack as a module
        cmd = night_rally.ReleaseCommand(params, release_params, "6.3.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        assert len(system_call.calls) == 2
        assert system_call.calls == [
            'rally --skip-update race --configuration-name="release" --quiet '
            '--target-host="localhost:9200" --effective-start-date="2016-01-01 00:00:00" '
            '--track-repository="default" --track="geonames" --challenge="append-no-conflicts" '
            '--car="defaults,trial-license,x-pack-security" --on-error="abort" '
            '--client-options="timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:\'rally\''
            ',basic_auth_password:\'rally-password\'" '
            "--user-tag=\"name:geonames-defaults,setup:bare-trial-security,race-configs-id:{},license:trial,"
            "x-pack:true,x-pack-components:security\" "
            '--runtime-jdk="8" --distribution-version="6.3.0" '
            '--pipeline="from-distribution"'.format(race_configs_id),

            'rally --skip-update race --configuration-name="release" --quiet '
            '--target-host="localhost:9200" --effective-start-date="2016-01-01 00:00:00" '
            '--track-repository="default" --track="geonames" --challenge="append-no-conflicts" '
            '--car="4gheap,trial-license,x-pack-security" --on-error="abort" '
            '--client-options="timeout:240,use_ssl:true,verify_certs:false,basic_auth_user:\'rally\''
            ',basic_auth_password:\'rally-password\'" '
            "--user-tag=\"name:geonames-4g-with-x-pack,setup:bare-trial-security,race-configs-id:{},license:trial,"
            "x-pack:true,x-pack-components:security\" "
            '--runtime-jdk="8" --distribution-version="6.3.0" '
            '--pipeline="from-distribution"'.format(race_configs_id)
        ]

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
        assert len(system_call.calls) == 1
        assert system_call.calls == [
            'rally --skip-update race --configuration-name="release" --quiet '
            '--target-host="localhost:9200" --effective-start-date="2016-01-01 00:00:00" '
            '--track-repository="default" --track="geonames" --challenge="append-no-conflicts" '
            '--car="defaults,basic-license" --on-error="abort" '
            '--client-options="timeout:240" '
            '--user-tag="name:geonames-defaults,setup:bare-basic,race-configs-id:{},license:basic" '
            '--runtime-jdk="8" '
            '--distribution-version="7.0.0" --pipeline="from-distribution"'.format(race_configs_id)
        ] 

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_release_benchmark_with_transport_nio(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)
        self.maxDiff = None

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
        release_params = OrderedDict({"license": "basic"})
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "bare-basic", race_configs_id=race_configs_id)]
        cmd = night_rally.ReleaseCommand(params, release_params, distribution_version="7.0.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        assert len(system_call.calls) == 1
        assert system_call.calls == [
            'rally --skip-update race --configuration-name="release" --quiet '
            '--target-host="localhost:9200" --effective-start-date="2016-01-01 00:00:00" '
            '--track-repository="default" --track="geonames" --challenge="append-no-conflicts" '
            '--car="defaults,unpooled,basic-license" --on-error="abort" '
            '--client-options="timeout:240" '
            '--user-tag="name:geonames-defaults,setup:bare-basic,race-configs-id:{},license:basic" '
            '--runtime-jdk="8" --elasticsearch-plugins="transport-nio:transport+http" '
            '--distribution-version="7.0.0" --pipeline="from-distribution"'.format(race_configs_id)
        ] 

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
        assert len(system_call.calls) == 0

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
        assert len(system_call.calls) == 0

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_do_not_run_release_benchmark_with_transport_nio_on_old_version(self, mocked_wait_until_port_is_free):
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
        release_params = {"license": "basic"}
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "bare-basic", race_configs_id=race_configs_id)]
        # 6.2.0 does not have transport-nio available
        cmd = night_rally.ReleaseCommand(params, release_params, distribution_version="6.2.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        assert len(system_call.calls) == 0

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_docker_5x_benchmark(self, mocked_wait_until_port_is_free):
        system_call = RecordingSystemCall(return_value=False)
        self.maxDiff = None
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
                            }
                        ]
                    }
                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        release_params = OrderedDict({"license": "basic"})
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "docker-basic", race_configs_id=race_configs_id)]
        cmd = night_rally.DockerCommand(params, release_params, "5.6.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        assert len(system_call.calls) == 2
        assert system_call.calls == [
            'rally --skip-update race --configuration-name="release" --quiet --target-host="localhost:9200" '
            '--effective-start-date="2016-01-01 00:00:00" --track-repository=\"default\" --track="geonames" '
            '--challenge="append-no-conflicts" --car="defaults" --on-error="abort" --client-options="timeout:240" '
            "--user-tag=\"name:geonames-defaults,setup:docker-basic,race-configs-id:{},license:basic\" "
            '--runtime-jdk="8" --distribution-version="5.6.0" '
            '--pipeline="docker" --car-params="{{\\"additional_cluster_settings\\": '
            '{{\\"xpack.security.enabled\\": \\"false\\", \\"xpack.ml.enabled\\": \\"false\\", '
            '\\"xpack.monitoring.enabled\\": \\"false\\", \\"xpack.watcher.enabled\\": \\"false\\"}}}}"'.format(race_configs_id),

            "rally --skip-update race --configuration-name=\"release\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"4gheap\" --on-error=\"abort\" --client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-4g,setup:docker-basic,race-configs-id:{},license:basic\" "
            "--runtime-jdk=\"8\" --distribution-version=\"5.6.0\" "
            "--pipeline=\"docker\" --car-params=\"{{\\\"additional_cluster_settings\\\": "
            "{{\\\"xpack.security.enabled\\\": \\\"false\\\", \\\"xpack.ml.enabled\\\": \\\"false\\\", "
            "\\\"xpack.monitoring.enabled\\\": \\\"false\\\", "
            "\\\"xpack.watcher.enabled\\\": \\\"false\\\"}}}}\"".format(race_configs_id),
        ]

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_docker_6x_benchmark(self, mocked_wait_until_port_is_free):
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
                            }
                        ]
                    }
                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        release_params = OrderedDict({"license": "basic"})
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "docker-basic", race_configs_id=race_configs_id)]
        cmd = night_rally.DockerCommand(params, release_params, "6.3.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        assert len(system_call.calls) == 2
        assert system_call.calls == [
            "rally --skip-update race --configuration-name=\"release\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults,basic-license\" --on-error=\"abort\" "
            "--client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-defaults,setup:docker-basic,race-configs-id:{},license:basic\" "
            "--runtime-jdk=\"8\" --distribution-version=\"6.3.0\" "
            "--pipeline=\"docker\"".format(race_configs_id),

            "rally --skip-update race --configuration-name=\"release\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"4gheap,basic-license\" --on-error=\"abort\" "
            "--client-options=\"timeout:240\" "
            "--user-tag=\"name:geonames-4g,setup:docker-basic,race-configs-id:{},license:basic\" "
            "--runtime-jdk=\"8\" --distribution-version=\"6.3.0\" "
            "--pipeline=\"docker\"".format(race_configs_id)
        ]

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_skip_any_plugins_with_docker(self, mocked_wait_until_port_is_free):
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
        release_params = OrderedDict({"license": "basic"})
        race_configs_id = os.path.basename(get_random_race_configs_id())
        params = [night_rally.StandardParams("release", start_date, 8, "docker-basic", race_configs_id=race_configs_id)]
        cmd = night_rally.DockerCommand(params, release_params, "7.3.0")

        night_rally.run_rally(tracks, release_params, ["localhost"], cmd, skip_ansible=True, system=system_call)
        assert len(system_call.calls) == 0

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_continues_on_error(self, mocked_wait_until_port_is_free):
        self.maxDiff = None
        system_call = RecordingSystemCall(return_value=True)

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
                                "name": "basic",
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

        assert len(system_call.calls) == 2
        assert system_call.calls == [
            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults,basic-license\" --on-error=\"abort\" "
            "--client-options=\"timeout:240\" --user-tag=\"name:geonames-defaults,setup:bare,license:basic\" "
            "--runtime-jdk=\"8\" --pipeline=\"from-sources\" --revision=\"@2016-10-01T00:00:00Z\"",

            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-10-01 00:00:00\" --track-repository=\"default\" --track=\"percolator\" "
            "--challenge=\"append-no-conflicts\" --car=\"4gheap,basic-license\" --on-error=\"abort\" "
            "--client-options=\"timeout:240\" --user-tag=\"name:percolator-4g,setup:bare,license:basic\" "
            "--runtime-jdk=\"8\" --pipeline=\"from-sources\" --revision=\"@2016-10-01T00:00:00Z\""
        ]

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_with_telemetry_from_command_line(self, mocked_wait_until_port_is_free):
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
        assert len(system_call.calls) == 1
        assert system_call.calls == [
            "rally --skip-update race --telemetry=\"jfr,gc,jit\" --telemetry-params=\"recording-template:profile\" "
            "--configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults,basic-license\" --on-error=\"abort\" "
            "--client-options=\"timeout:240\" --user-tag=\"name:geonames-defaults,setup:bare,license:basic\" "
            "--runtime-jdk=\"8\" --pipeline=\"from-sources\" --revision=\"@2016-01-01T00:00:00Z\""
        ]

    @mock.patch('night_rally.night_rally.wait_until_port_is_free', return_value=True)
    def test_run_with_telemetry_from_race_config(self, mocked_wait_until_port_is_free):
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
                                        "car": "defaults",
                                        "telemetry": ["jfr", "gc", "jit"],
                                        "telemetry-params": {
                                            "recording-template": "profile"
                                        }
                                    },
                                    {
                                        "name": "geonames-4g",
                                        "challenge": "append-no-conflicts",
                                        "car": "4gheap",
                                        "telemetry": "gc"
                                    },
                                    {
                                        "name": "geonames-8g",
                                        "challenge": "append-no-conflicts",
                                        "car": "8gheap",
                                        "on-error": "continue"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
        start_date = datetime.datetime(2016, 1, 1)
        params = [night_rally.StandardParams("nightly", start_date, 8, "bare")]

        cmd = night_rally.NightlyCommand(params, start_date)

        night_rally.run_rally(tracks, None, ["localhost"], cmd, skip_ansible=True, system=system_call)
        assert len(system_call.calls) == 3
        assert system_call.calls == [
            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"defaults,basic-license\" --on-error=\"abort\" "
            "--client-options=\"timeout:240\" --user-tag=\"name:geonames-defaults,setup:bare,license:basic\" "
            "--runtime-jdk=\"8\" --telemetry=\"jfr,gc,jit\" --telemetry-params=\"{\\\"recording-template\\\": \\\"profile\\\"}\" "
            "--pipeline=\"from-sources\" --revision=\"@2016-01-01T00:00:00Z\"",

            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"4gheap,basic-license\" --on-error=\"abort\" "
            "--client-options=\"timeout:240\" --user-tag=\"name:geonames-4g,setup:bare,license:basic\" "
            "--runtime-jdk=\"8\" --telemetry=\"gc\" --pipeline=\"from-sources\" --revision=\"@2016-01-01T00:00:00Z\"",

            "rally --skip-update race --configuration-name=\"nightly\" --quiet --target-host=\"localhost:9200\" "
            "--effective-start-date=\"2016-01-01 00:00:00\" --track-repository=\"default\" --track=\"geonames\" "
            "--challenge=\"append-no-conflicts\" --car=\"8gheap,basic-license\" --on-error=\"continue\" "
            "--client-options=\"timeout:240\" --user-tag=\"name:geonames-8g,setup:bare,license:basic\" "
            "--runtime-jdk=\"8\" --pipeline=\"from-sources\" --revision=\"@2016-01-01T00:00:00Z\"",
        ]

    @mock.patch("night_rally.client.create_client")
    def test_finds_race_meta_data(self, client_factory):
        race = {
            "rally-version": "1.4.2.dev0 (git revision: 321b158)",
            "rally-revision": "321b158",
            "environment": "nightly",
            "trial-id": "6a7527a5-79ba-4cbf-a41c-d09a4b254b2a",
            "trial-timestamp": "20200310T200052Z",
            "race-id": "6a7527a5-79ba-4cbf-a41c-d09a4b254b2a",
            "race-timestamp": "20200310T200000Z",
            "pipeline": "from-sources",
            "user-tags": {
                "name": "geonames-append-4g-3nodes",
                "setup": "bare-oss",
                "race-configs-id": "race-configs-group-1.json",
                "license": "oss"
            },
            "track": "geonames",
            "car": ["4gheap"],
            "cluster": {
                "revision": "1073d09363f5355bd86ac63ca9580d1f677c604e",
                "distribution-version": "8.0.0-SNAPSHOT",
                "distribution-flavor": "oss",
                "team-revision": "cb01613"
            },
            "track-revision": "abc6e72",
            "challenge": "append-no-conflicts-index-only",
            "track-params": {
                "number_of_replicas": 1
            }
        }

        es = mock.Mock()
        es.search.return_value = {
            "took": 2,
            "timed_out": False,
            "_shards": {
                "total": 1,
                "successful": 1,
                "skipped": 0,
                "failed": 0
            },
            "hits": {
                "total": {
                    "value": 352
                },
                "hits": [
                    {
                        "_index": "rally-races-2020-03",
                        "_type": "_doc",
                        "_id": "6a7527a5-79ba-4cbf-a41c-d09a4b254b2a",
                        "_source": race,
                        "sort": [
                            1583870452000
                        ]
                    }
                ]
            }
        }

        client_factory.return_value = es

        meta_data = night_rally.race_meta_data(environment="nightly",
                                               configuration_name="nightly",
                                               effective_start_date=datetime.datetime(year=2020, month=3, day=10, hour=20),
                                               race_configs_id="race-configs-group-1.json",
                                               previous=False,
                                               dry_run=False)
        assert meta_data == race

        es.search.assert_called_once_with(index="rally-races-*", body={
            "query": {
                "bool": {
                    "filter": [
                        {
                            "term": {
                                "environment": "nightly"
                            }
                        },
                        {
                            "range": {
                                "race-timestamp": {
                                    "lte": "20200310T200000Z"
                                }
                            }
                        },
                        {
                            "term": {
                                "user-tags.race-configs-id": "race-configs-group-1.json"
                            }
                        }
                    ]
                }
            },
            "size": 1,
            "sort": [
                {
                    "race-timestamp": {
                        "order": "desc"
                    }
                }
            ]
        })
