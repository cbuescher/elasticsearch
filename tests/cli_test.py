import unittest
import os.path

from night_rally import night_rally
from tests import get_random_race_configs_id


class CommonCliParamsTests(unittest.TestCase):
    default_mode = "nightly"
    default_version = "master"
    default_release_license = "basic"
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

        self.assertEqual("bare-basic", common_cli_params.setup)
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
        self.assertEqual("bare-basic", common_cli_params.setup)
        self.assertEqual("release", common_cli_params.configuration_name)
        self.assertEqual("6.6.0", common_cli_params.version)
        self.assertEqual({"license": "basic"}, common_cli_params.release_params)
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
            release_license="basic",
            release_x_pack_components=CommonCliParamsTests.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        self.assertFalse(common_cli_params.is_nightly)
        self.assertTrue(common_cli_params.is_release)
        self.assertFalse(common_cli_params.is_adhoc)
        self.assertFalse(common_cli_params.is_docker)

        self.assertTrue(common_cli_params.release_params)
        self.assertEqual("ear-basic", common_cli_params.setup)
        self.assertEqual("release", common_cli_params.configuration_name)
        self.assertEqual("6.2.1", common_cli_params.version)
        self.assertEqual({
            "license": "basic"
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
            release_license="basic",
            release_x_pack_components=CommonCliParamsTests.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        self.assertFalse(common_cli_params.is_nightly)
        self.assertTrue(common_cli_params.is_release)
        self.assertFalse(common_cli_params.is_adhoc)
        self.assertTrue(common_cli_params.is_docker)

        self.assertTrue(common_cli_params.release_params)
        self.assertEqual("docker-basic", common_cli_params.setup)
        self.assertEqual("release", common_cli_params.configuration_name)
        self.assertEqual("6.2.2", common_cli_params.version)
        self.assertTrue({
            "license": "basic"
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
                release_license="basic",
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
            release_license="trial",
            release_x_pack_components=CommonCliParamsTests.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        self.assertFalse(common_cli_params.is_nightly)
        self.assertFalse(common_cli_params.is_release)
        self.assertTrue(common_cli_params.is_adhoc)
        self.assertFalse(common_cli_params.is_docker)

        self.assertFalse(common_cli_params.release_params)
        self.assertEqual("bare-trial", common_cli_params.setup)
        self.assertEqual("adhoc", common_cli_params.configuration_name)
        self.assertEqual("lucene-7", common_cli_params.version)
        self.assertFalse(common_cli_params.release_params)
        self.assertEqual(os.path.basename(race_configs_id), common_cli_params.race_configs_id)
