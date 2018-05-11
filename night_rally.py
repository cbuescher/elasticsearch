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

ROOT = os.path.dirname(os.path.realpath(__file__))
RALLY_BINARY = "rally --skip-update"

VERSION_PATTERN = re.compile("^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$")

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
    class SourcePipelineParams:
        def __init__(self):
            self.default_dist_pipeline = "from-sources-complete"
            self.oss_dist_pipeline = "from-sources-complete"

        def __call__(self, race_config):
            if race_config.x_pack:
                pipeline = self.default_dist_pipeline
                # after we've executed the first benchmark, there is no reason to build again from sources
                self.default_dist_pipeline = "from-sources-skip-build"
                # as we clean the other distribution (implicitly) by building now, we need to rebuild next time again
                self.oss_dist_pipeline = "from-sources-complete"
            else:
                pipeline = self.oss_dist_pipeline
                self.oss_dist_pipeline = "from-sources-skip-build"
                self.default_dist_pipeline = "from-sources-complete"
            return {"pipeline": pipeline}

    def __init__(self, params, revision):
        self.params = ParamsFormatter(params=params + [
            XPackParams(distribution_version="master"),
            SourceBasedCommand.SourcePipelineParams(),
            ConstantParam("revision", revision)
        ])


class NightlyCommand(SourceBasedCommand):
    def __init__(self, params, effective_start_date):
        super().__init__(params, "@%s" % to_iso8601(effective_start_date))


class AdHocCommand(SourceBasedCommand):
    def __init__(self, params, revision):
        super().__init__(params, revision)


class ReleaseCommand(BaseCommand):
    def __init__(self, params, x_pack_config, distribution_version):
        self.distribution_version = distribution_version
        self.params = ParamsFormatter(params=params + [
            XPackParams(distribution_version, x_pack_config),
            ConstantParam("distribution-version", distribution_version),
            ConstantParam("pipeline", "from-distribution")
        ])

    def runnable(self, race_config):
        # Do not run 1g benchmarks at all at the moment. Earlier versions of ES OOM.
        if race_config.car == "1gheap":
            return False
        # Do not run with special x-pack configs. We run either the whole suite with or without x-pack.
        if race_config.x_pack:
            return False
        # noaa does not work on older versions. This should actually be specified in track.json and not here...
        if int(self.distribution_version[0]) < 5 and race_config.track == "noaa":
            return False
        # cannot run "sorted" challenges - it's a 6.0+ feature
        if int(self.distribution_version[0]) < 6 and "sorted" in race_config.challenge:
            return False
        return True


class DockerCommand(BaseCommand):
    def __init__(self, params, distribution_version):
        self.pipeline = "docker"
        self.distribution_version = distribution_version
        self.params = ParamsFormatter(params=params + [
            ConstantParam("distribution-version", distribution_version),
            ConstantParam("pipeline", "docker")
        ])

    def runnable(self, race_config):
        # we don't support (yet?) clusters with multiple Docker containers
        if len(race_config.target_hosts) > 1:
            return False
        # we are not interested in those metrics for Docker
        if race_config.car in ["verbose_iw"]:
            return False
        # no plugin installs on Docker
        if race_config.x_pack:
            return False
        # cannot run "sorted" challenges - it's a 6.0+ feature
        if int(self.distribution_version[0]) < 6:
            return "sorted" not in race_config.challenge
        return True


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
                    # treat as array first, then join them later
                    cmd_line_params[k] = cmd_line_params[k] + v
                else:
                    cmd_line_params[k] = v

        cmd = RALLY_BINARY
        for k, v in cmd_line_params.items():
            if isinstance(v, list):
                cmd += " --{}=\"{}\"".format(k, join_nullables(*v))
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
    def __init__(self, configuration_name, effective_start_date, user_tag):
        self.configuration_name = configuration_name
        self.effective_start_date = effective_start_date
        self.user_tag = user_tag

    def __call__(self, race_config):
        params = {
            "configuration-name": self.configuration_name,
            "quiet": None,
            "target-host": race_config.target_hosts,
            "effective-start-date": self.effective_start_date,
            "track": race_config.track,
            "challenge": race_config.challenge,
            "car": [race_config.car],
            "user-tag": self.format_tag(additional_tags={"name": race_config.name})
        }
        add_if_present(params, "car-params", race_config.car_params)
        add_if_present(params, "track-params", race_config.track_params)
        return params

    def format_tag(self, additional_tags=None):
        final_tags = {}
        final_tags.update(self.user_tag)
        if additional_tags:
            final_tags.update(additional_tags)
        return ["{}:{}".format(k, v) for k, v in final_tags.items()]


class XPackParams:
    """
    Extracts all parameters that are relevant for benchmarking with x-pack. Before Elasticsearch 6.3.0 x-pack is considered a plugin.
    For later versions it is treated as module.
    """
    def __init__(self, distribution_version, override_x_pack=None):
        if distribution_version == "master":
            self.treat_as_car = True
        else:
            major, minor, _, _ = components(distribution_version)
            self.treat_as_car = major > 6 or (major == 6 and minor >= 3)

        self.distribution_version = distribution_version
        self.override_x_pack = override_x_pack

    def __call__(self, race_config):
        params = {}
        x_pack = self.override_x_pack if self.override_x_pack else race_config.x_pack
        add_if_present(params, "client-options", self.client_options(x_pack))
        add_if_present(params, "elasticsearch-plugins", self.elasticsearch_plugins(x_pack))
        add_if_present(params, "car", self.car(x_pack))
        add_if_present(params, "user-tag", self.user_tags(x_pack))
        return params

    def client_options(self, x_pack):
        if x_pack and "security" in x_pack:
            return "timeout:60,use_ssl:true,verify_certs:false,basic_auth_user:'rally',basic_auth_password:'rally-password'"
        else:
            return None

    def elasticsearch_plugins(self, x_pack):
        if x_pack and not self.treat_as_car:
            return "x-pack:{}".format(",".join(x_pack))
        else:
            return None

    def car(self, x_pack):
        if x_pack and self.treat_as_car:
            return ["x-pack-{}".format(cfg) for cfg in x_pack]
        else:
            return None

    def user_tags(self, x_pack):
        if x_pack:
            return ["x-pack:true"]
        else:
            return None


class RaceConfig:
    def __init__(self, track_name, combination, available_hosts):
        self.track = track_name
        self.combination = combination
        self.available_hosts = available_hosts

    @property
    def name(self):
        return self.combination["name"]

    @property
    def node_count(self):
        return self.combination.get("node-count", 1)

    @property
    def challenge(self):
        return self.combination["challenge"]

    @property
    def car(self):
        return self.combination["car"]

    @property
    def car_params(self):
        return self.combination.get("car-params")

    @property
    def plugins(self):
        return self.combination.get("plugins", "")

    @property
    def track_params(self):
        return self.combination.get("track-params")

    @property
    def x_pack(self):
        return self.combination.get("x-pack")

    @property
    def target_hosts(self):
        if self.node_count > len(self.available_hosts):
            return None
        else:
            return self.available_hosts[:self.node_count]

    def __str__(self):
        return self.name


def run_rally(tracks, available_hosts, command, dry_run=False, skip_ansible=False, system=os.system):
    rally_failure = False
    if dry_run:
        runner = logger.info
    else:
        runner = system
    for track in tracks:
        track_name = track["track"]
        for combination in track["combinations"]:
            race_cfg = RaceConfig(track_name, combination, available_hosts)

            if race_cfg.target_hosts:
                if command.runnable(race_cfg):
                    if not skip_ansible:
                        logger.info("Resetting benchmark environment...")
                        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "ansible")
                        shell_command = "cd {} && " \
                                        "ansible-playbook -i inventory/production -u rally playbooks/setup.yml " \
                                        "--tags={} && cd -".format(fixtures_dir,
                                                                   shlex.quote("drop-caches,trim"))
                        runner(shell_command)
                    logger.info("Running Rally on [%s]", race_cfg)
                    start = time.perf_counter()
                    try:
                        wait_until_port_is_free(available_hosts)
                        if runner(command.command_line(race_cfg)):
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

def copy_results_for_release_comparison(effective_start_date, dry_run):
    import client
    es = client.create_client()

    if not dry_run:
        import elasticsearch.helpers
        """
        Copies all results in the metric store for the given trial timestamp so that they are also available as master release results.
        """
        es.indices.refresh(index="rally-results-*")
        ts = to_iso8601_short(effective_start_date)
        # find all of today's results but exclude "x-pack" ones because we will not have release charts for them (x-pack has
        # their own dedicated trial runs on releases)
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "trial-timestamp": {
                                    "value": ts
                                }
                            }
                        }
                    ],
                    "must_not": [
                        {
                            "term": {
                                # see XPackParams#user_tags()
                                "user-tags.x-pack": {
                                    "value": "true"
                                }
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
            # as we query for a specific trial timestamp, all documents are in the same index
            index = hit["_index"]
            doc_type = hit["_type"]
            src = hit["_source"]
            # pseudo version for stable comparisons
            src["distribution-version"] = "master"
            src["environment"] = "release"
            release_results.append(src)
        if release_results:
            logger.info("Copying %d result documents for [%s] to release environment." % (len(release_results), ts))
            elasticsearch.helpers.bulk(es, release_results, index=index, doc_type=doc_type)


def deactivate_outdated_results(effective_start_date, environment, release, env_tag, dry_run):
    """
    Sets all results for the same major release version, environment and tag to active=False except for the records with the provided
    effective start date.
    """
    import client
    es = client.create_client()
    ts = to_iso8601_short(effective_start_date)
    logger.info("Activating results only for [%s] on [%s] in environment [%s] and tag [%s]." % (release, ts, environment, env_tag))
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
                        "trial-timestamp": ts
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

    if env_tag and "env" in env_tag:
        body["query"]["bool"]["filter"].append({
            "term": {
                "user-tags.env": env_tag["env"]
            }
        })
    if dry_run:
        import json
        logger.info("Would execute update query script\n%s" % json.dumps(body, indent=2))
    else:
        es.indices.refresh(index="rally-results-*")
        res = es.update_by_query(index="rally-results-*", body=body, size=10000)
        logger.info("Result: %s" % res)


def parse_args():
    parser = argparse.ArgumentParser(prog="night_rally", description="Nightly Elasticsearch benchmarks")

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
        "--x-pack",
        help="X Pack components to benchmark",
        default="")
    parser.add_argument(
        "--fixtures",
        help="A comma-separated list of fixtures that have been run",
        required=True)
    parser.add_argument(
        "--dry-run",
        help="Does not do anything, just output",
        default=False,
        action="store_true")
    parser.add_argument(
        "--mode",
        help="In which mode to run?",
        default="nightly",
        choices=["nightly", "release", "adhoc"])
    parser.add_argument(
        "--revision",
        help="Specify the source code revision to build for adhoc benchmarks.",
        default="latest")
    parser.add_argument(
        "--release",
        help="Specify release string to use for comparison reports",
        default="master")
    parser.add_argument(
        "--tracks",
        help="Path to the tracks.json file that contains the tracks to run",
        default=None)
    parser.add_argument(
        "--telemetry",
        help="Rally telemetry to activate",
        default=None)
    parser.add_argument(
        "--telemetry-params",
        help="Parameters of Rally telemetry to set",
        default=None)

    return parser.parse_args()


def load_tracks(tracks):
    import json
    path = tracks if tracks else "%s/resources/tracks.json" % ROOT
    with open(path, mode="rt", encoding="utf-8") as tracks_file:
        return json.load(tracks_file)


def main():
    args = parse_args()

    start_date = args.effective_start_date
    logger.info("Effective start date is [%s]" % date_for_cmd_param(start_date))

    release_mode = args.mode == "release"
    adhoc_mode = args.mode == "adhoc"
    nightly_mode = args.mode == "nightly"
    env_name = sanitize(args.mode)

    x_pack = args.x_pack.split(",") if args.x_pack else None
    target_hosts = args.target_host.split(",")

    docker_benchmark = args.release.startswith("Docker ")
    release = args.release.replace("Docker ", "")

    if "encryption-at-rest" in args.fixtures:
        release_tag = {"env": "ear"}
    elif x_pack:
        release_tag = {"env": "x-pack"}
    elif docker_benchmark:
        release_tag = {"env": "docker"}
    else:
        release_tag = {"env": "bare"}

    tracks = load_tracks(args.tracks)
    params = []

    if args.telemetry:
        logger.info("Activating Rally telemetry %s." % args.telemetry)
        params.append(TelemetryParams(args.telemetry, args.telemetry_params))

    if release_mode:
        params.append(StandardParams(env_name, start_date, release_tag))
        if docker_benchmark:
            if x_pack:
                raise RuntimeError("User specified x-pack configuration [%s] but this is not supported for Docker benchmarks." % x_pack)
            logger.info("Running Docker release benchmarks for release [%s] against %s." % (release, target_hosts))
            command = DockerCommand(params, release)
        else:
            logger.info("Running release benchmarks for release [%s] against %s (release tag is [%s])."
                        % (release, target_hosts, release_tag))
            command = ReleaseCommand(params, x_pack, release)
    elif adhoc_mode:
        logger.info("Running adhoc benchmarks for revision [%s] against %s." % (args.revision, target_hosts))
        params.append(StandardParams(env_name, start_date, release_tag))
        command = AdHocCommand(params, args.revision)
    else:
        logger.info("Running nightly benchmarks against %s." % target_hosts)
        params.append(StandardParams(env_name, start_date, release_tag))
        command = NightlyCommand(params, start_date)

    rally_failure = run_rally(tracks, target_hosts, command, args.dry_run, args.skip_ansible)

    if nightly_mode:
        copy_results_for_release_comparison(start_date, args.dry_run)
        # we want to deactivate old release entries, not old nightly entries
        deactivate_outdated_results(start_date, "release", release, release_tag, args.dry_run)
    elif release_mode:
        deactivate_outdated_results(start_date, env_name, release, release_tag, args.dry_run)
    if rally_failure:
        exit(1)


if __name__ == "__main__":
    main()
