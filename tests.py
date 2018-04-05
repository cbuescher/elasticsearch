import datetime
import unittest

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


class NightRallyTests(unittest.TestCase):
    def test_sanitize(self):
        self.assertEqual("lucene-7-upgrade", night_rally.sanitize("Lucene 7 Upgrade"))
        self.assertEqual("lucene-7-upgrade", night_rally.sanitize("lucene-7-upgrade"))
        self.assertEqual("elasticsearch-6_0_0-alpha1-docker", night_rally.sanitize("Elasticsearch 6.0.0-alpha1 Docker"))

    def test_run_two_challenges_successfully(self):
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
        cmd = night_rally.NightlyCommand(start_date, {"env": "bare"})
        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=nightly --target-host=\"localhost\" --pipeline=from-sources-complete --quiet "
                "--revision \"@2016-01-01T00:00:00Z\" --effective-start-date \"2016-01-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=defaults --user-tag=\"env:bare,name:geonames-defaults\"",

                "rally --skip-update --configuration-name=nightly --target-host=\"localhost\" --pipeline=from-sources-skip-build --quiet "
                "--revision \"@2016-01-01T00:00:00Z\" --effective-start-date \"2016-01-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=4gheap --user-tag=\"env:bare,name:geonames-4g\""
            ]
            ,
            system_call.calls
        )

    def test_run_two_tracks_successfully(self):
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
        cmd = night_rally.NightlyCommand(start_date, {"env": "bare"})
        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=nightly --target-host=\"localhost\" --pipeline=from-sources-complete --quiet "
                "--revision \"@2016-10-01T00:00:00Z\" --effective-start-date \"2016-10-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=defaults --user-tag=\"env:bare,name:geonames-defaults\"",

                "rally --skip-update --configuration-name=nightly --target-host=\"localhost\" --pipeline=from-sources-skip-build --quiet "
                "--revision \"@2016-10-01T00:00:00Z\" --effective-start-date \"2016-10-01 00:00:00\" --track=percolator "
                "--challenge=append-no-conflicts --car=4gheap --user-tag=\"env:bare,name:percolator-4g\""]
            ,
            system_call.calls
        )

    def test_run_adhoc_benchmark(self):
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
        cmd = night_rally.AdHocCommand("66202dc", start_date, "lucene-7", {"env": "bare"})
        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=lucene-7 --target-host=\"localhost\" --pipeline=from-sources-complete --quiet "
                "--revision \"66202dc\" --effective-start-date \"2016-10-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=defaults --user-tag=\"env:bare,name:geonames-defaults\"",
                
                "rally --skip-update --configuration-name=lucene-7 --target-host=\"localhost\" --pipeline=from-sources-skip-build --quiet "
                "--revision \"66202dc\" --effective-start-date \"2016-10-01 00:00:00\" --track=percolator "
                "--challenge=append-no-conflicts --car=4gheap --user-tag=\"env:bare,name:percolator-4g\""]
            ,
            system_call.calls
        )

    def test_run_release_benchmark_without_plugins(self):
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
        cmd = night_rally.ReleaseCommand(start_date, None, "5.3.0", "release", user_tag={"env": "bare"})
        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=release --target-host=\"localhost\" --pipeline=from-distribution --quiet "
                "--distribution-version=5.3.0 --effective-start-date \"2016-01-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=defaults "
                "--user-tag=\"env:bare,name:geonames-defaults\"",

                "rally --skip-update --configuration-name=release --target-host=\"localhost\" --pipeline=from-distribution --quiet "
                "--distribution-version=5.3.0 --effective-start-date \"2016-01-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=4gheap "
                "--user-tag=\"env:bare,name:geonames-4g\""
            ]
            ,
            system_call.calls
        )

    def test_run_release_benchmark_with_plugins(self):
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
        cmd = night_rally.ReleaseCommand(start_date, "x-pack:security,monitoring", "5.3.0", "release", user_tag={"env": "x-pack"})
        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=release --target-host=\"localhost\" --pipeline=from-distribution --quiet "
                "--distribution-version=5.3.0 --effective-start-date \"2016-01-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=defaults "
                "--user-tag=\"env:x-pack,name:geonames-defaults\" --elasticsearch-plugins=\"x-pack:security,monitoring\" --cluster-health=yellow "
                "--client-options=\"timeout:60,use_ssl:true,verify_certs:false,basic_auth_user:'rally',basic_auth_password:'rally-password'\"",

                "rally --skip-update --configuration-name=release --target-host=\"localhost\" --pipeline=from-distribution --quiet "
                "--distribution-version=5.3.0 --effective-start-date \"2016-01-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=4gheap "
                "--user-tag=\"env:x-pack,name:geonames-4g\" --elasticsearch-plugins=\"x-pack:security,monitoring\" --cluster-health=yellow "
                "--client-options=\"timeout:60,use_ssl:true,verify_certs:false,basic_auth_user:'rally',basic_auth_password:'rally-password'\"",
            ]
            ,
            system_call.calls
        )

    def test_run_docker_benchmark(self):
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
        cmd = night_rally.DockerCommand(start_date, "5.3.0", "release", {"env": "docker"})
        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=release --target-host=\"localhost\" --pipeline=docker --quiet "
                "--distribution-version=5.3.0 --effective-start-date \"2016-01-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=defaults "
                "--user-tag=\"env:docker,name:geonames-defaults\" --cluster-health=yellow",

                "rally --skip-update --configuration-name=release --target-host=\"localhost\" --pipeline=docker --quiet "
                "--distribution-version=5.3.0 --effective-start-date \"2016-01-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=4gheap "
                "--user-tag=\"env:docker,name:geonames-4g\" --cluster-health=yellow"
            ]
            ,
            system_call.calls
        )

    def test_run_continues_on_error(self):
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
        cmd = night_rally.NightlyCommand(start_date, {"env": "bare"})
        night_rally.run_rally(tracks, ["localhost"], cmd, skip_ansible=True, system=system_call)

        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --skip-update --configuration-name=nightly --target-host=\"localhost\" --pipeline=from-sources-complete --quiet "
                "--revision \"@2016-10-01T00:00:00Z\" --effective-start-date \"2016-10-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=defaults --user-tag=\"env:bare,name:geonames-defaults\"",

                "rally --skip-update --configuration-name=nightly --target-host=\"localhost\" --pipeline=from-sources-skip-build --quiet "
                "--revision \"@2016-10-01T00:00:00Z\" --effective-start-date \"2016-10-01 00:00:00\" --track=percolator "
                "--challenge=append-no-conflicts --car=4gheap --user-tag=\"env:bare,name:percolator-4g\""]
            ,
            system_call.calls
        )


if __name__ == '__main__':
    unittest.main()
