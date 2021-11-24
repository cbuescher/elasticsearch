import os.path

from night_rally import night_rally
from tests import get_random_race_configs_id


class TestCommonCliParams():
    default_mode = "nightly"
    default_version = "master"
    default_release_license = "trial"
    default_release_x_pack_components = "security"

    def test_parses_defaults(self):
        race_configs_id = get_random_race_configs_id()

        common_cli_params = night_rally.CommonCliParams(
            mode=self.default_mode,
            configuration_name="nightly",
            version=self.default_version,
            release_license=self.default_release_license,
            release_x_pack_components=self.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        assert common_cli_params.is_nightly
        assert not common_cli_params.is_release
        assert not common_cli_params.is_adhoc
        assert not common_cli_params.is_docker
        assert not common_cli_params.release_params

        assert common_cli_params.setup == "bare"
        assert common_cli_params.configuration_name == "nightly"
        assert common_cli_params.version == "master"
        assert not common_cli_params.release_params
        assert common_cli_params.race_configs_id == os.path.basename(race_configs_id)

    def test_parses_release_6_6_0(self):
        race_configs_id = get_random_race_configs_id()

        common_cli_params = night_rally.CommonCliParams(
            mode="release",
            configuration_name="release",
            version="6.6.0",
            release_license=self.default_release_license,
            release_x_pack_components=self.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        assert not common_cli_params.is_nightly
        assert common_cli_params.is_release
        assert not common_cli_params.is_adhoc
        assert not common_cli_params.is_docker

        assert common_cli_params.release_params
        assert common_cli_params.setup == "bare"
        assert common_cli_params.configuration_name == "release"
        assert common_cli_params.version == "6.6.0"
        assert common_cli_params.release_params == {"license": "trial", "x-pack-components": ["security"]} 
        assert common_cli_params.race_configs_id == os.path.basename(race_configs_id) 

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

        assert not common_cli_params.is_nightly
        assert common_cli_params.is_release
        assert not common_cli_params.is_adhoc
        assert not common_cli_params.is_docker

        assert common_cli_params.release_params
        assert common_cli_params.setup == "bare"
        assert common_cli_params.configuration_name == "release"
        assert common_cli_params.version == "6.5.3"
        assert common_cli_params.release_params == {"license": "trial", "x-pack-components": ["security"]} 
        assert common_cli_params.race_configs_id == os.path.basename(race_configs_id) 

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

        assert not common_cli_params.is_nightly
        assert common_cli_params.is_release
        assert not common_cli_params.is_adhoc
        assert not common_cli_params.is_docker

        assert common_cli_params.release_params
        # TODO: be specific about additional plugins
        assert common_cli_params.setup == "bare"
        assert common_cli_params.configuration_name == "release"
        assert common_cli_params.version == "6.5.1"
        assert common_cli_params.release_params == {
            "license": "trial",
            "x-pack-components": ["security","monitoring"],
        }
        assert common_cli_params.race_configs_id == os.path.basename(race_configs_id) 

    def test_parses_release_ear_6_2_1(self):
        race_configs_id = get_random_race_configs_id()

        common_cli_params = night_rally.CommonCliParams(
            mode="release:encryption-at-rest",
            configuration_name="release",
            version="6.2.1",
            release_license="trial",
            release_x_pack_components=self.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        assert not common_cli_params.is_nightly
        assert common_cli_params.is_release
        assert not common_cli_params.is_adhoc
        assert not common_cli_params.is_docker

        assert common_cli_params.release_params
        assert common_cli_params.setup == "ear"
        assert common_cli_params.configuration_name == "release"
        assert common_cli_params.version == "6.2.1"
        assert common_cli_params.release_params == {"license": "trial", "x-pack-components": ["security"]} 
        assert common_cli_params.race_configs_id == os.path.basename(race_configs_id) 

    def test_parses_docker_release_6_2_2(self):
        race_configs_id = get_random_race_configs_id()

        common_cli_params = night_rally.CommonCliParams(
            mode="release:docker",
            configuration_name="release",
            version="6.2.2",
            release_license="trial",
            release_x_pack_components=self.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        assert not common_cli_params.is_nightly
        assert common_cli_params.is_release
        assert not common_cli_params.is_adhoc
        assert common_cli_params.is_docker

        assert common_cli_params.release_params
        assert common_cli_params.setup == "docker"
        assert common_cli_params.configuration_name == "release"
        assert common_cli_params.version == "6.2.2"
        assert common_cli_params.release_params == {"license": "trial", "x-pack-components": ["security"]} 
        assert common_cli_params.race_configs_id == os.path.basename(race_configs_id) 

    def test_parses_adhoc_benchmarks(self):
        race_configs_id = get_random_race_configs_id()

        common_cli_params = night_rally.CommonCliParams(
            mode="adhoc",
            configuration_name="adhoc",
            version="lucene-7",
            release_license="trial",
            release_x_pack_components=self.default_release_x_pack_components,
            race_configs_id=race_configs_id
        )

        assert not common_cli_params.is_nightly
        assert not common_cli_params.is_release
        assert common_cli_params.is_adhoc
        assert not common_cli_params.is_docker

        assert not common_cli_params.release_params
        assert common_cli_params.setup == "bare"
        assert common_cli_params.configuration_name == "adhoc"
        assert common_cli_params.version == "lucene-7"
        assert not common_cli_params.release_params
        assert common_cli_params.race_configs_id == os.path.basename(race_configs_id) 
