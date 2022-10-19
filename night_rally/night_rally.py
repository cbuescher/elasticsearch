import argparse
import collections
import datetime
import errno
import logging
import os
import re
import shlex
import socket
import time
import inspect
import json
import jsonschema

ROOT = os.path.dirname(os.path.realpath(__file__))
RALLY_BINARY = "rally --skip-update race"
VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$")
# The port that Elasticsearch is configured to use for rest requests.
TARGET_HTTP_PORT = 9200
TARGET_TRANSPORT_PORT = 9300
RACE_CONFIGS_SCHEMA_FILE = "{}/resources/race-configs-schema.json".format(ROOT)

MIN_ES_VERSION_PER_TRACK = {
    "eql": 7,
    "solutions/logs": 7,
    "geopointshape": 7,
    "dense_vector": 8
}

# console logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s][%(levelname)s] %(message)s")
# Remove all handlers associated with the root logger object so we can start over with an entirely fresh log configuration
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

log_level = logging.INFO
ch = logging.StreamHandler()
ch.setLevel(log_level)
formatter = logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
formatter.converter = time.gmtime
ch.setFormatter(formatter)
logging.root.addHandler(ch)

logger = logging.getLogger("night_rally")


class NightRallyError(Exception):
    """
    Base class for all Night Rally exceptions
    """

    def __init__(self, message, cause=None):
        super().__init__(message, cause)
        self.message = message
        self.cause = cause

    def __repr__(self):
        return self.message


class RemotePortNotFree(NightRallyError):
    """
    Thrown whenever the specified port in --target-host is not free
    """


class RemotePortNotDefined(NightRallyError):
    """
    Thrown whenever there was no port specified in --target-host
    """


def run_track(track, es_major_ver):
    """
    Determines whether to run or skip track depending on the major version of Elasticsearch
    """

    return int(es_major_ver) >= MIN_ES_VERSION_PER_TRACK.get(track, -1)


def wait_until_port_is_free(target_hosts, connector=socket, wait_time=5):
    max_attempts = 5
    attempt = 1
    port_free = True
    connect_result = None

    from elasticsearch.client import _normalize_hosts
    for node in _normalize_hosts(target_hosts):
        if "port" not in node:
            raise RemotePortNotDefined(
                message="No port specified for target host: [{}]. Please check your target-host parameter.".format(node["host"]),
                cause="Missing target port error."
            )

        while attempt <= max_attempts:
            c = connector.socket()
            connect_result = c.connect_ex((node["host"], node["port"]))
            try:
                if connect_result == errno.ECONNREFUSED:
                    port_free = True
                    c.close()
                    break
                else:
                    port_free = False
                    logger.info("Port [%s] on host [%d] is not free. "
                                "Waiting for %d seconds now, attempt %d/%d.",
                                node["host"],
                                node["port"],
                                wait_time,
                                attempt,
                                max_attempts)
                    c.close()
                    time.sleep(wait_time)
                    attempt += 1
            except OSError:
                logger.exception(
                    "Ignoring error while trying to close the socket after connecting to "
                    "node: [{}:{}]".format(node["host"],
                                           node["port"]))
        if not port_free:
            # target host port occupied or some other socket error
            raise RemotePortNotFree(
                message="Port [{}] on host [{}] is not free, "
                "or another persistent issue while attempting to connect to it.".format(node["port"], node["host"]),
                cause="errno = {}".format(connect_result if connect_result == 0 else errno.errorcode[connect_result]))

    return port_free


def date_for_cmd_param(d):
    return "{:%Y-%m-%d %H:%M:%S}".format(d)


def to_iso8601(d):
    """
    Convert a datetime instance to a ISO-8601 compliant string.
    :param d: A datetime instance (assuming timezone UTC)
    :return: The corresponding ISO-8601 formatted string
    """
    return "{:%Y-%m-%dT%H:%M:%SZ}".format(d)


def to_iso8601_short(d):
    return "{:%Y%m%dT%H%M%SZ}".format(d)


def sanitize(text):
    """
    Sanitizes the input text so it is safe to use as an environment name in Rally.

    :param text: A text to sanitize
    """
    return text.lower().replace(" ", "-").replace(".", "_")


def csv_to_list(csv):
    """
    Converts a comma-separated string into a list.
    """
    if csv is None:
        return None
    elif len(csv.strip()) == 0:
        return []
    else:
        return [e.strip() for e in csv.split(",")]


def join_nullables(*args, join_with=","):
    """

    Joins the provided arguments by ``join_with``.

    :param args: Arguments to join. Arguments needs to be either ``str`` or None. Arguments that are ``None`` will be skipped.
    :param join_with: The string that should be used to join individual elements.
    :return: A string containing all arguments that are not ``None`` joined by ``join_with``.
    """
    return join_with.join(filter(None, args))


def components(version):
    """
    Determines components of a version string.

    :param version: A version string in the format major.minor.path-suffix (suffix is optional)
    :return: A tuple with four components determining "major", "minor", "patch" and "suffix" (any part except "major" may be `None`)
    """
    matches = VERSION_PATTERN.match(version)
    if matches:
        if matches.start(4) > 0:
            return int(matches.group(1)), int(matches.group(2)), int(matches.group(3)), matches.group(4)
        elif matches.start(3) > 0:
            return int(matches.group(1)), int(matches.group(2)), int(matches.group(3)), None
        elif matches.start(2) > 0:
            return int(matches.group(1)), int(matches.group(2)), None, None
        elif matches.start(1) > 0:
            return int(matches.group(1)), None, None, None
        else:
            return int(version), None, None, None
    raise ValueError("version string '{}' does not conform to pattern '{}'".format(version, VERSION_PATTERN.pattern))


class BaseCommand:
    def runnable(self, race_config):
        return True

    def command_line(self, race_config):
        return self.params.command_line(race_config)


class SourceBasedCommand(BaseCommand):
    def __init__(self, params, revision):
        self.params = ParamsFormatter(params=params + [
            LicenseParams(distribution_version="master"),
            ConstantParam("pipeline", "from-sources"),
            ConstantParam("revision", revision)
        ])


class DistributionBasedCommand(BaseCommand):
    def __init__(self, params, distribution_version, release_params=None):
        self.params = ParamsFormatter(params=params + [
            LicenseParams(distribution_version, release_params),
            ConstantParam("distribution-version", distribution_version),
            ConstantParam("pipeline", "from-distribution")
        ])


class NightlyCommand(SourceBasedCommand):
    def __init__(self, params, effective_start_date):
        super().__init__(params, "@%s" % to_iso8601(effective_start_date))


class ParamsFormatter:
    """
    Renders the provided (structured) command line parameters as a Rally invocation.
    """
    def __init__(self, params):
        self.params = params

    def command_line(self, race_config):
        cmd_line_params = collections.OrderedDict()
        for p in self.params:
            for k, v in p(race_config).items():
                if k in cmd_line_params:
                    if isinstance(v, dict):
                        cmd_line_params[k].update(v)
                    else:
                        # treat as array first, then join them later
                        cmd_line_params[k] = cmd_line_params[k] + v
                else:
                    if isinstance(v, dict):
                        cmd_line_params[k] = collections.OrderedDict()
                        cmd_line_params[k].update(v)
                    else:
                        cmd_line_params[k] = v

        cmd = RALLY_BINARY
        for k, v in cmd_line_params.items():
            if isinstance(v, list):
                cmd += " --{}=\"{}\"".format(k, join_nullables(*v))
            elif isinstance(v, dict):
                cmd += " --{}=\"{}\"".format(k, json.dumps(v).replace('"', '\\"'))
            elif v is None:
                cmd += " --{}".format(k)
            else:
                cmd += " --{}=\"{}\"".format(k, v)

        return cmd


def add_if_present(d, k, v):
    if v:
        d[k] = v


class TelemetryParams:
    """
    Extracts telemetry-related parameters.
    """
    def __init__(self, telemetry, telemetry_params):
        self.telemetry = telemetry
        self.telemetry_params = telemetry_params

    def __call__(self, race_config):
        params = {
            "telemetry": self.telemetry
        }
        if self.telemetry_params:
            params["telemetry-params"] = self.telemetry_params
        return params


class ConstantParam:
    """
    Extracts a single constant parameter which is provided externally as a key-value pair.
    """
    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __call__(self, race_config):
        return {self.key: self.value}


class StandardParams:
    """
    Extracts all parameters that are needed for all Rally invocations.
    """
    def __init__(self, configuration_name, effective_start_date, runtime_jdk, user_tag_setup, race_configs_id=None, test_mode=False):
        self.configuration_name = configuration_name
        self.effective_start_date = effective_start_date
        self.runtime_jdk = runtime_jdk
        self.user_tag_setup = user_tag_setup
        self.race_configs_id = race_configs_id
        self.test_mode = test_mode

    def __call__(self, race_config):
        params = {
            "configuration-name": self.configuration_name,
            "quiet": None,
            "target-host": race_config.target_hosts,
            "effective-start-date": self.effective_start_date,
            "track-repository": race_config.track_repository,
            "track": race_config.track,
            "challenge": race_config.challenge,
            "car": race_config.car,
            "on-error": "abort",
            "client-options": "timeout:240"
        }

        additional_tags = {
            "name": race_config.name,
            "setup": self.user_tag_setup}
        if self.race_configs_id:
            additional_tags["race-configs-id"] = self.race_configs_id
        params["user-tag"] = self.tags(additional_tags=additional_tags)

        if race_config.runtime_jdk:
            params["runtime-jdk"] = race_config.runtime_jdk
        else:
            add_if_present(params, "runtime-jdk", self.runtime_jdk)
        add_if_present(params, "telemetry", race_config.telemetry)
        add_if_present(params, "telemetry-params", race_config.telemetry_params)
        add_if_present(params, "exclude-tasks", race_config.exclude_tasks)
        add_if_present(params, "car-params", race_config.car_params)
        add_if_present(params, "track-params", race_config.track_params)
        add_if_present(params, "on-error", race_config.on_error)
        add_if_present(params, "elasticsearch-plugins", race_config.plugins)
        if self.test_mode:
            params["test-mode"] = None
        return params

    def tags(self, additional_tags=None):
        final_tags = {}
        if additional_tags:
            final_tags.update(additional_tags)
        return ["{}:{}".format(k, v) for k, v in final_tags.items()]


class LicenseParams:
    """
    Extracts all license related parameters that affect benchmarking. Before Elasticsearch 6.3.0 x-pack is considered a plugin.
    For later versions it is treated as module.
    """
    def __init__(self, distribution_version, release_params=None):
        if distribution_version == "master":
            self.treat_as_car = True
        else:
            major, minor, _, _ = components(distribution_version)
            self.treat_as_car = major > 6 or (major == 6 and minor >= 3)

        self.distribution_version = distribution_version
        self.release_params = release_params

    def __call__(self, race_config):
        params = {}
        x_pack = race_config.x_pack
        if self.release_params:
            for component in self.release_params.get("x-pack-components", []):
                if component not in x_pack:
                    x_pack.append(component)

        add_if_present(params, "client-options", self.client_options(x_pack))
        add_if_present(params, "elasticsearch-plugins", self.elasticsearch_plugins(x_pack))
        add_if_present(params, "car", self.car(x_pack, race_config.license))
        add_if_present(params, "user-tag", self.user_tags(x_pack, race_config.license))
        return params

    def client_options(self, x_pack):
        if x_pack and "security" in x_pack:
            # will get merged with standard options; XPackParams is not meant to be used standalone.
            return ",use_ssl:true,verify_certs:false,basic_auth_user:'rally',basic_auth_password:'rally-password'"
        else:
            return None

    def elasticsearch_plugins(self, x_pack):
        if x_pack and not self.treat_as_car:
            return "x-pack:{}".format("+".join(x_pack))
        else:
            return None

    def car(self, x_pack, track_license=None):
        car = []
        effective_track_license = self.release_params["license"] if self.release_params else track_license

        if self.treat_as_car and "oss" not in effective_track_license:
            car.append("{}-license".format(effective_track_license))
            if x_pack:
                car += ["x-pack-{}".format(cfg) for cfg in x_pack]
        else:
            return None

        return car

    def user_tags(self, x_pack, track_license):
        effective_track_license = self.release_params["license"] if self.release_params else track_license

        user_tags = ["license:{}".format(effective_track_license)]
        if x_pack:
            user_tags += ["x-pack:true"]
        if self.release_params and "x-pack-components" in self.release_params:
            user_tags += ["x-pack-components:{}".format(",".join(self.release_params["x-pack-components"]))]
        return user_tags


class RaceConfig:
    def __init__(self, track_name, track_repository, placement, configuration, available_hosts):
        self.track = track_name
        self.track_repository = track_repository
        self.placement = placement
        self.configuration = configuration
        self.available_hosts = available_hosts

    @property
    def name(self):
        return self.configuration["name"]

    @property
    def license(self):
        return self.configuration["license"]

    @property
    def node_count(self):
        return self.configuration.get("node-count", 1)

    @property
    def challenge(self):
        return self.configuration["challenge"]

    @property
    def car(self):
        c = self.configuration["car"]
        return self._as_array(c)

    @property
    def car_params(self):
        return self.configuration.get("car-params")
    
    @property
    def exclude_tasks(self):
        return self.configuration.get("exclude-tasks")

    @property
    def plugins(self):
        return self.configuration.get("plugins", "")
    
    @property
    def telemetry(self):
        t = self.configuration.get("telemetry")
        return self._as_array(t)
    
    @property
    def telemetry_params(self):
        return self.configuration.get("telemetry-params")

    @property
    def runtime_jdk(self):
        return self.configuration.get("runtime-jdk")

    @property
    def track_params(self):
        return self.configuration.get("track-params")

    @property
    def on_error(self):
        return self.configuration.get("on-error")

    @property
    def x_pack(self):
        return self.configuration.get("x-pack", [])

    @property
    def target_hosts(self):
        if self.node_count > len(self.available_hosts):
            return None
        elif self.node_count == len(self.available_hosts):
            return self.available_hosts
        else:
            d = collections.deque(self.available_hosts)
            d.rotate(-self.placement)
            return list(d)[:self.node_count]

    def _as_array(self, v):
        if isinstance(v, str):
            return [v]
        else:
            return v

    def __str__(self):
        return "{}-{}".format(self.license, self.name)


def validate_race_configs(race_configs):
    with open(RACE_CONFIGS_SCHEMA_FILE, mode="rt", encoding="utf-8") as f:
        race_configs_schema = json.loads(f.read())

    jsonschema.validate(race_configs, race_configs_schema)


def run_rally(race_configs, release_params, available_hosts, command, dry_run=False, skip_ansible=False, system=os.system):
    # Build list of host:port pairs for target hosts
    available_hosts_with_http_ports = list(map(lambda h: f"{h}:{TARGET_HTTP_PORT}", available_hosts))
    available_hosts_with_transport_ports = list(map(lambda h: f"{h}:{TARGET_TRANSPORT_PORT}", available_hosts))
    rally_failure = False
    if dry_run:
        runner = logger.info
    else:
        runner = system

    for r in race_configs:
        track_name = r["track"]
        placement = r.get("placement", 0)
        track_repository = r.get("track-repository", "default")

        for configuration in r["configurations"]:

            # security by default, unless adhoc options are set
            configuration["license"] = release_params["license"] if release_params else "trial"
            race_cfg = RaceConfig(track_name, track_repository, placement, configuration, available_hosts_with_http_ports)
    
            if race_cfg.target_hosts:
                if command.runnable(race_cfg):
                    if not skip_ansible:
                        logger.info("Resetting benchmark environment...")
                        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "ansible")
                        shell_command = "cd {} && " \
                                        "ansible-playbook -i inventory/production -u rally playbooks/setup.yml " \
                                        "--tags={} && cd - >/dev/null".format(fixtures_dir,
                                                                              shlex.quote("drop-caches,trim"))
                        runner(shell_command)
                    logger.info("Running Rally on [%s]", race_cfg)
                    start = time.perf_counter()
                    try:
                        if not dry_run:
                            wait_until_port_is_free(available_hosts_with_http_ports)
                            wait_until_port_is_free(available_hosts_with_transport_ports)
                        cmd = command.command_line(race_cfg)
                        logger.info("Executing [%s]", cmd)
                        if runner(cmd):
                            rally_failure = True
                            logger.error("Failed to run [%s]. Please check the logs.", race_cfg)
                        stop = time.perf_counter()
                        logger.info("Finished running on [%s] in [%f] seconds.", race_cfg, (stop - start))
                    except (RemotePortNotFree, RemotePortNotDefined) as remote_port_exception:
                        logger.error("Skipped running [%s].", race_cfg)
                        logger.error(remote_port_exception.message)
                        logger.error(remote_port_exception.cause)
                        break
                else:
                    logger.info("Skipping [%s] (not supported by command).", race_cfg)
            else:
                logger.info("Skipping [%s] (not enough target machines available).", race_cfg)
    return rally_failure


#################################################
# Reporting
#################################################

def copy_results_for_release_comparison(effective_start_date, configuration_name, race_configs_id, dry_run):
    from night_rally import client
    es = client.create_client(configuration_name)

    if not dry_run:
        import elasticsearch.helpers
        """
        Copies all results in the metric store for the given timestamp so that they are also available as master release results.
        """
        es.indices.refresh(index="rally-results-*")
        ts = to_iso8601_short(effective_start_date)
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "race-timestamp": {
                                    "value": ts
                                }
                            }
                        },
                        # also limit by environment in case of multiple night-rally jobs executed at the same time using different env
                        {
                            "term": {
                                "environment": configuration_name
                            }
                        },
                        # and avoid race conditions with >1 night-rally invocations on different hardware using same environment
                        {
                              "term": {
                                  "user-tags.race-configs-id": race_configs_id
                              }
                        }
                    ]
                }
            }
        }
        result = es.search(index="rally-results-*", body=query, size=10000)

        release_results = []
        index = None
        doc_type = None
        for hit in result["hits"]["hits"]:
            # as we query for a specific race timestamp, all documents are in the same index
            index = hit["_index"]
            doc_type = hit["_type"]
            src = hit["_source"]
            # pseudo version for stable comparisons
            src["distribution-version"] = "master"
            src["environment"] = "release"
            # release benchmarks rely on `user-tags.setup` for bar charts
            src["user-tags"]["setup"] = "bare"
            release_results.append(src)
        if release_results:
            logger.info("Copying %d result documents for [%s] to release environment." % (len(release_results), ts))
            elasticsearch.helpers.bulk(es, release_results, index=index, doc_type=doc_type)


def deactivate_outdated_results(effective_start_date, configuration_name, release, release_tag, race_configs_id, dry_run, environment=None):
    """
    Sets all results for the same major release version, environment, tag and race_configs_id to active=False except for the records
    with the provided effective start date.
    """
    ts = to_iso8601_short(effective_start_date)
    if not environment:
        # for release benchmarks environment is explicitly set to release
        environment = configuration_name
    logger.info("Activating results only for [%s] on [%s] in environment [%s], tag [%s] and race-config-id [%s]." %
                (release, ts, environment, release_tag, race_configs_id))
    body = {
        "script": {
            "source": "ctx._source.active = false",
            "lang": "painless"
        },
        "query": {
            "bool": {
                "filter": [
                    {
                        "term": {
                            "active": True
                        }
                    },
                    {
                        "term": {
                            "environment": environment
                        }
                    }
                ],
                "must_not": {
                    "term": {
                        "race-timestamp": ts
                    }
                }
            }
        }
    }
    if release == "master":
        body["query"]["bool"]["filter"].append({
            "term": {
                "distribution-version": release
            }
        })
    else:
        body["query"]["bool"]["filter"].append({
            "term": {
                "distribution-major-version": int(release[:release.find(".")])
            }
        })

    if release_tag:
        body["query"]["bool"]["filter"].append({
            "term": {
                "user-tags.setup": release_tag
            }
        })

    # TODO: refactor to be more generic in the future. For now, we don't deactivate results belonging to a different target-group
    if race_configs_id:
        body["query"]["bool"]["filter"].append({
            "term": {
                "user-tags.race-configs-id": race_configs_id
            }
        })

    if dry_run:
        import json
        logger.info("Would execute update query script\n%s" % json.dumps(body, indent=2))
    else:
        from night_rally import client
        es = client.create_client(configuration_name)
        es.indices.refresh(index="rally-results-*")
        res = es.update_by_query(index="rally-results-*", body=body)
        logger.info("Result: %s" % res)


def race_meta_data(environment, configuration_name, effective_start_date, race_configs_id, previous, dry_run):
    """

    :param environment: The environment's name (e.g. "nightly")
    :param configuration_name: The Rally configuration name (which usually matches the environment name)
    :param effective_start_date: The effective start date as datetime.
    :param race_configs_id: Race config id for which to retrieve the race meta-data.
    :param previous: A bool indicating whether to retrieve details about the race *prior* to the one provided via
                     ``effective_start_date`` (``previous=True``) or whether to retrieve details about the current
                     race (``previous=False``).
    :param dry_run: A bool indicating whether to only simulate retrieval (``dry_run=True``).
    :return: The matching race meta-data or ``None`` if there is no match.
    """
    ts_filter = "lt" if previous else "lte"

    query = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "term": {
                            "environment": environment
                        }
                    },
                    {
                        "range": {
                            "race-timestamp": {
                                ts_filter: to_iso8601_short(effective_start_date)
                            }
                        }
                    },
                    {
                        "term": {
                            "user-tags.race-configs-id": race_configs_id
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
    }
    if dry_run:
        import json
        logger.info("Would execute query\n%s" % json.dumps(query, indent=2))
        return None
    else:
        import json
        from night_rally import client
        es = client.create_client(configuration_name)
        es.indices.refresh(index="rally-races-*")
        logger.debug("Executing query\n%s" % json.dumps(query, indent=2))
        result = es.search(index="rally-races-*", body=query)
        logger.debug("Got %s results.", str(result["hits"]["total"]["value"]))
        if result["hits"]["total"]["value"] > 0:
            return result["hits"]["hits"][0]["_source"]
        else:
            return None


def non_empty_string(v):
    if isinstance(v, str):
        if not v:
            raise argparse.ArgumentTypeError("must be non-empty")
    else:
        raise argparse.ArgumentTypeError("[{}] must be a string.".format(v))
    return v


def parse_args():
    parser = argparse.ArgumentParser(prog="es-night-rally", description="Nightly Elasticsearch benchmarks")

    parser.add_argument(
        "--effective-start-date",
        help="Passes this date as start date to Rally (format: %%Y-%%m-%%d %%H:%%M:%%S). Needed for consistent results for multiple "
             "trial runs",
        required=True,
        type=lambda s: datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S"))
    parser.add_argument(
        "--skip-ansible",
        help=argparse.SUPPRESS,
        default=False,
        action="store_true")
    parser.add_argument(
        "--target-host",
        help="The Elasticsearch node that should be targeted",
        required=True)
    parser.add_argument(
        "--test-mode",
        help="Use --test-mode with Rally i.e. use 1k corpus in all invocations",
        action="store_true",
        default=False)
    parser.add_argument(
        "--dry-run",
        help="Does not do anything, just output",
        default=False,
        action="store_true")
    parser.add_argument(
        "--environment",
        help="The name of the benchmarking environment")
    parser.add_argument(
        "--mode",
        help="In which mode to run?",
        default="nightly",
        choices=["nightly", "adhoc", "release", "release:docker", "release:encryption-at-rest", "release:x-pack"])
    parser.add_argument(
        "--revision",
        help="Specify the source code revision to build for adhoc benchmarks.",
        default="latest")
    parser.add_argument(
        "--version",
        help="Specify release string to use for comparison reports.",
        default="master")
    parser.add_argument(
        "--release-license",
        help="Specify license to use for release benchmarks.",
        default="basic")
    parser.add_argument(
        "--release-x-pack-components",
        help="Comma separated list of x-pack components to use with release or adhoc benchmarks; example: security.",
        default="basic")
    parser.add_argument(
        "--runtime-jdk",
        help="The major version of the runtime JDK to use.",
        required=True,
        type=non_empty_string,
        default=None)
    parser.add_argument(
        "--race-configs",
        help="Relative path to the json file that contains the race configs to run. "
             "The path is relative to <night_rally_repo>/night_rally e.g. resources/race-configs-group-1.json",
        required=True,
        type=non_empty_string,
        default=None)
    parser.add_argument(
        "--telemetry",
        help="Rally telemetry to activate. Applies to all race configs, any additional telemetry specified in a race "
             "configuration will be appended. Mixing telemetry devices in cli and race configs will result "
             "in duplicate definitions.",
        default=None)
    parser.add_argument(
        "--telemetry-params",
        help="Parameters of Rally telemetry to set. Applies to all race configs, any additional params specified "
             "in a race configuration will be appended. Mixing telemetry params in cli and race configs will result "
             "in duplicate definitions.",
        default=None)

    return parser.parse_args()


def load_race_configs(race_configs):
    path = os.path.join(ROOT, race_configs)
    with open(path, mode="rt", encoding="utf-8") as race_configs_file:
        race_configs_json = json.load(race_configs_file)
    validate_race_configs(race_configs_json)
    return race_configs_json


class CommonCliParams:
    """
    Extracts all release specific parameteres needed for all Rally invocations.
    """

    def __init__(self,
                 mode="nightly",
                 version="master",
                 configuration_name=None,
                 release_license=None,
                 release_x_pack_components=None,
                 race_configs_id=None
                 ):
        self.version = version
        self._mode = mode
        self.configuration_name = configuration_name
        self.release_params = collections.OrderedDict()
        self._release_x_pack_components = release_x_pack_components
        self._release_license = release_license
        # For now only used for release benchmarks
        self.setup = self.__build_setup_string()

        # Store the filename of race_configs (e.g. `race-configs-group-1.json`)
        # we need it in user tags to help deactivating old release results
        self.race_configs_id = os.path.basename(race_configs_id)

    def __build_setup_string(self):
        # is in the form "<bare|ear|docker>"
        # examples: "bare", "ear"
        setup = "bare"
        if "encryption-at-rest" in self._mode:
            setup = "ear"
        elif self.is_docker:
            setup = "docker"

        return setup

    @property
    def is_nightly(self):
        return self._mode.startswith("nightly")

    @property
    def is_release(self):
        return self._mode.startswith("release")

    @property
    def is_docker(self):
        return self._mode.endswith("docker")

    @property
    def is_adhoc(self):
        return self._mode == "adhoc"

    @property
    def printable_release_params(self):
        return dict(self.release_params)


def main():
    args = parse_args()
    start_date = args.effective_start_date
    logger.info("Effective start date is [%s]" % date_for_cmd_param(start_date))

    version_to_benchmark = args.version
    common_cli_params = CommonCliParams(
        mode=args.mode,
        version=version_to_benchmark,
        configuration_name=args.environment,
        release_license=args.release_license,
        release_x_pack_components=args.release_x_pack_components,
        race_configs_id=args.race_configs
    )

    target_hosts = args.target_host.split(",")
    race_configs = load_race_configs(args.race_configs)
    params = []

    if args.telemetry:
        logger.info("Activating Rally telemetry %s." % args.telemetry)
        params.append(TelemetryParams(csv_to_list(args.telemetry), csv_to_list(args.telemetry_params)))

    if common_cli_params.is_adhoc:
        params.append(StandardParams(common_cli_params.configuration_name, start_date, args.runtime_jdk,
                                     common_cli_params.setup, args.test_mode))
        if args.version is not None and args.version != "master":
            logger.info("Running adhoc benchmarks for version [%s] against %s." % (args.version, target_hosts))
            command = DistributionBasedCommand(params, args.version)
        else:
            logger.info("Running adhoc benchmarks for revision [%s] against %s." % (args.revision, target_hosts))
            command = SourceBasedCommand(params, args.revision)
    else:
        logger.info("Running nightly benchmarks against %s." % target_hosts)
        params.append(StandardParams(common_cli_params.configuration_name, start_date, args.runtime_jdk,
                                     common_cli_params.setup, common_cli_params.race_configs_id, args.test_mode))
        command = NightlyCommand(params, start_date)

    rally_failure = run_rally(race_configs, common_cli_params.release_params, target_hosts, command, args.dry_run, args.skip_ansible)

    if common_cli_params.is_nightly:
        copy_results_for_release_comparison(
            start_date,
            common_cli_params.configuration_name,
            common_cli_params.race_configs_id,
            args.dry_run
        )

        previous = race_meta_data("nightly",
                                  common_cli_params.configuration_name,
                                  start_date,
                                  common_cli_params.race_configs_id,
                                  previous=True,
                                  dry_run=args.dry_run)
        current = race_meta_data("nightly",
                                 common_cli_params.configuration_name,
                                 start_date,
                                 common_cli_params.race_configs_id,
                                 previous=False,
                                 dry_run=args.dry_run)

        if previous and current:
            # be lenient here and always assume that key are absent (may happen due to changes in the data model)
            msg = """Changes between [{previous_ts}] and [{current_ts}]:
            
            * Elasticsearch: https://github.com/elastic/elasticsearch/compare/{previous_es}...{current_es}
            * Rally: https://github.com/elastic/rally/compare/{previous_rally}...{current_rally}
            * rally-tracks: https://github.com/elastic/rally-tracks/compare/{previous_tracks}...{current_tracks}
            * rally-teams: https://github.com/elastic/rally-teams/compare/{previous_teams}...{current_teams}
            """.format(previous_ts=previous.get("race-timestamp"),
                       current_ts=current.get("race-timestamp"),
                       previous_es=previous.get("cluster", {}).get("revision"),
                       current_es=current.get("cluster", {}).get("revision"),
                       previous_rally=previous.get("rally-revision"),
                       current_rally=current.get("rally-revision"),
                       previous_tracks=previous.get("track-revision"),
                       current_tracks=current.get("track-revision"),
                       previous_teams=previous.get("cluster", {}).get("team-revision"),
                       current_teams=current.get("cluster", {}).get("team-revision"),
                       )
            logger.info(inspect.cleandoc(msg))
        else:
            logger.info("Cannot determine race meta-data. Skipping summary.")

    if rally_failure:
        exit(1)


if __name__ == "__main__":
    main()
