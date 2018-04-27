import argparse
import datetime
import logging
import os
import time

ROOT = os.path.dirname(os.path.realpath(__file__))
RALLY_BINARY = "rally --skip-update"

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
    :param join_with: The string that should be used to join invidivual elements.
    :return: A string containing all arguments that are not ``None`` joined by ``join_with``.
    """
    return join_with.join(filter(None, args))


class BaseCommand:
    def __init__(self, effective_start_date, user_tag):
        self.effective_start_date = effective_start_date
        self.ts = date_for_cmd_param(effective_start_date)
        self.user_tag = user_tag

    def runnable(self, track, challenge, car, plugins, target_hosts):
        return True

    def command_line(self, track, track_params, challenge, car, name, plugins, target_hosts):
        raise NotImplementedError("abstract method")

    def format_tag(self, additional_tags=None):
        final_tags = {}
        final_tags.update(self.user_tag)
        if additional_tags:
            final_tags.update(additional_tags)
        return ",".join(["%s:%s" % (k, v) for k, v in final_tags.items()])


class SourceBasedCommand(BaseCommand):
    def __init__(self, effective_start_date, revision, configuration_name, user_tag):
        super().__init__(effective_start_date, user_tag)
        self.revision = revision
        self.configuration_name = configuration_name
        self.default_dist_pipeline = "from-sources-complete"
        self.oss_dist_pipeline = "from-sources-complete"

    def command_line(self, track, track_params, challenge, car, name, plugins, target_hosts):
        x_pack = "x-pack-security" in car

        cmd = RALLY_BINARY
        cmd += " --configuration-name=%s" % self.configuration_name
        cmd += " --target-host=\"%s\"" % ",".join(target_hosts)
        if x_pack:
            cmd += " --pipeline=%s" % self.default_dist_pipeline
            # after we've executed the first benchmark, there is no reason to build again from sources
            self.default_dist_pipeline = "from-sources-skip-build"
        else:
            cmd += " --pipeline=%s" % self.oss_dist_pipeline
            self.oss_dist_pipeline = "from-sources-skip-build"

        cmd += " --quiet"
        cmd += " --revision \"%s\"" % self.revision
        cmd += " --effective-start-date \"%s\"" % self.effective_start_date
        cmd += " --track=%s" % track
        if x_pack:
            cmd += " --client-options=\"timeout:60,use_ssl:true,verify_certs:false,basic_auth_user:'rally',basic_auth_password:'rally-password'\""
            track_params = join_nullables(track_params, "cluster_health:'yellow'")

        if track_params:
            cmd += " --track-params=\"%s\"" % track_params
        cmd += " --challenge=%s" % challenge
        cmd += " --car=\"%s\"" % car
        cmd += " --user-tag=\"%s\"" % self.format_tag(additional_tags={"name": name})

        if plugins:
            cmd += " --elasticsearch-plugins=\"%s\"" % plugins
        return cmd


class NightlyCommand(SourceBasedCommand):
    CONFIG_NAME = "nightly"

    def __init__(self, effective_start_date, user_tag):
        super().__init__(effective_start_date, "@%s" % to_iso8601(effective_start_date),
                         NightlyCommand.CONFIG_NAME, user_tag)


class AdHocCommand(SourceBasedCommand):
    def __init__(self, revision, effective_start_date, configuration_name, user_tag):
        super().__init__(effective_start_date, revision, configuration_name, user_tag)


class ReleaseCommand(BaseCommand):
    def __init__(self, effective_start_date, plugins, distribution_version, configuration_name, user_tag):
        super().__init__(effective_start_date, user_tag)
        self.plugins = plugins
        self.configuration_name = configuration_name
        self.pipeline = "from-distribution"
        self.distribution_version = distribution_version

    def runnable(self, track, challenge, car, plugins, target_hosts):
        # Do not run 1g benchmarks at all at the moment. Earlier versions of ES OOM.
        if car == "1gheap":
            return False
        # Do not run plugin-specific tracks. We run either the whole suite with or without plugins.
        if plugins != "":
            return False
        # noaa does not work on older versions. This should actually be specified in track.json and not here...
        if int(self.distribution_version[0]) < 5 and track == "noaa":
            return False
        # cannot run "sorted" challenges - it's a 6.0+ feature
        if int(self.distribution_version[0]) < 6 and "sorted" in challenge:
            return False
        return True

    def command_line(self, track, track_params, challenge, car, name, plugins, target_hosts):
        cmd = RALLY_BINARY
        cmd += " --configuration-name=%s" % self.configuration_name
        cmd += " --target-host=\"%s\"" % ",".join(target_hosts)
        cmd += " --pipeline=%s" % self.pipeline
        cmd += " --quiet"
        cmd += " --distribution-version=%s" % self.distribution_version
        cmd += " --effective-start-date \"%s\"" % self.effective_start_date
        cmd += " --track=%s" % track
        if self.plugins and "x-pack:security" in self.plugins:
            track_params = join_nullables(track_params, "cluster_health:'yellow'")
        if track_params:
            cmd += " --track-params=\"%s\"" % track_params
        cmd += " --challenge=%s" % challenge
        cmd += " --car=%s" % car
        cmd += " --user-tag=\"%s\"" % self.format_tag(additional_tags={"name": name})

        # note that we will only run with the plugins provided externally but not with plugins provided via track.json!
        if self.plugins:
            cmd += " --elasticsearch-plugins=\"%s\"" % self.plugins
            if "x-pack:security" in self.plugins:
                cmd += " --client-options=\"timeout:60,use_ssl:true,verify_certs:false,basic_auth_user:'rally',basic_auth_password:'rally-password'\""

        return cmd


class DockerCommand(BaseCommand):
    def __init__(self, effective_start_date, distribution_version, configuration_name, user_tag):
        super().__init__(effective_start_date, user_tag)
        self.configuration_name = configuration_name
        self.pipeline = "docker"
        self.distribution_version = distribution_version

    def runnable(self, track, challenge, car, plugins, target_hosts):
        # we don't support (yet?) clusters with multiple Docker containers
        if len(target_hosts) > 1:
            return False
        # we are not interested in those metrics for Docker
        if car in ["verbose_iw"]:
            return False
        # no plugin installs on Docker
        if plugins != "":
            return False
        # cannot run "sorted" challenges - it's a 6.0+ feature
        if int(self.distribution_version[0]) < 6:
            return "sorted" not in challenge
        return True

    def command_line(self, track, track_params, challenge, car, name, plugins, target_hosts):
        cmd = RALLY_BINARY
        cmd += " --configuration-name=%s" % self.configuration_name
        cmd += " --target-host=\"%s\"" % ",".join(target_hosts)
        cmd += " --pipeline=%s" % self.pipeline
        cmd += " --quiet"
        cmd += " --distribution-version=%s" % self.distribution_version
        cmd += " --effective-start-date \"%s\"" % self.effective_start_date
        cmd += " --track=%s" % track
        # due to the possibility that x-pack is active (that depends on Rally)
        cmd += " --track-params=\"%s\"" % join_nullables(track_params, "cluster_health:'yellow'")
        cmd += " --challenge=%s" % challenge
        cmd += " --car=%s" % car
        cmd += " --user-tag=\"%s\"" % self.format_tag(additional_tags={"name": name})
        return cmd


class TelemetryDecorator:
    def __init__(self, command, telemetry, telemetry_params):
        self.command = command
        self.telemetry = telemetry
        self.telemetry_params = telemetry_params

    def runnable(self, *args):
        return self.command.runnable(*args)

    def command_line(self, *args):
        cmd_line = self.command.command_line(*args)
        cmd_line += " --telemetry=\"{}\"".format(self.telemetry)
        if self.telemetry_params:
            cmd_line += " --telemetry-params=\"{}\"".format(self.telemetry_params)
        return cmd_line


def choose_target_hosts(available_hosts, node_count):
    if node_count > len(available_hosts):
        return None
    else:
        return available_hosts[:node_count]


def run_rally(tracks, available_hosts, command, dry_run=False, skip_ansible=False, system=os.system):
    rally_failure = False
    if dry_run:
        runner = logger.info
    else:
        runner = system
    for track in tracks:
        track_name = track["track"]
        for combination in track["combinations"]:
            challenge = combination["challenge"]
            car = combination["car"]
            name = combination["name"]
            node_count = combination.get("node-count", 1)
            target_hosts = choose_target_hosts(available_hosts, node_count)
            plugins = combination.get("plugins", "")
            track_params = combination.get("track-params")
            info = race_info(track_name, challenge, car, plugins, node_count)
            if target_hosts:
                if command.runnable(track_name, challenge, car, plugins, target_hosts):
                    if not skip_ansible:
                        logger.info("Resetting benchmark environment...")
                        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "ansible")
                        runner("cd \"%s\" && ansible-playbook -i inventory/production -u rally playbooks/setup.yml "
                               "--tags=\"drop-caches,trim\" && cd -" % fixtures_dir)
                    logger.info("Running Rally on %s" % info)
                    start = time.perf_counter()
                    if runner(command.command_line(track_name, track_params, challenge, car, name, plugins, target_hosts)):
                        rally_failure = True
                        logger.error("Failed to run %s. Please check the logs." % info)
                    stop = time.perf_counter()
                    logger.info("Finished running on %s in [%f] seconds." % (info, (stop - start)))
                else:
                    logger.info("Skipping %s (not supported by command)." % info)
            else:
                logger.info("Skipping %s (not enough target machines available)." % info)
    return rally_failure


def race_info(track, challenge, car, plugins, node_count):
    if plugins:
        msg = "track [%s] with challenge [%s], car [%s] and plugins [%s]" % (track, challenge, car, plugins)
    else:
        msg = "track [%s] with challenge [%s] and car [%s]" % (track, challenge, car)
    if node_count > 1:
        msg += " on %d nodes" % node_count
    else:
        msg += " on one node"
    return msg


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
                                "plugins": {
                                    "value": "x-pack"
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
            # TODO: Provided for backwards-compatibility (otherwise all graphs would break immediately). Remove me once graphs are migrated.
            src["user-tag"] = "env:bare"
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
        "--elasticsearch-plugins",
        help="Elasticsearch plugins to install for the benchmark (default: None)",
        default=None)
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

    plugins = args.elasticsearch_plugins
    target_hosts = args.target_host.split(",")

    docker_benchmark = args.release.startswith("Docker ")
    release = args.release.replace("Docker ", "")

    if "encryption-at-rest" in args.fixtures:
        release_tag = {"env": "ear"}
    elif "x-pack:security" in plugins:
        release_tag = {"env": "x-pack"}
    elif docker_benchmark:
        release_tag = {"env": "docker"}
    else:
        release_tag = {"env": "bare"}

    tracks = load_tracks(args.tracks)

    if release_mode:
        # use always the same name for release comparison benchmarks
        env_name = sanitize(args.mode)
        if docker_benchmark:
            if plugins:
                raise RuntimeError("User specified plugins [%s] but this is not supported for Docker benchmarks." % plugins)
            logger.info("Running Docker release benchmarks for release [%s] against %s." % (release, target_hosts))
            command = DockerCommand(start_date, release, env_name, release_tag)
        else:
            logger.info("Running release benchmarks for release [%s] against %s (release tag is [%s])."
                        % (release, target_hosts, release_tag))
            command = ReleaseCommand(start_date, plugins, release, env_name, release_tag)
    elif adhoc_mode:
        logger.info("Running adhoc benchmarks for revision [%s] against %s." % (args.revision, target_hosts))
        # copy data from templates directory to our dedicated output directory
        env_name = sanitize(args.release)
        command = AdHocCommand(args.revision, start_date, env_name, release_tag)
    else:
        logger.info("Running nightly benchmarks against %s." % target_hosts)
        env_name = NightlyCommand.CONFIG_NAME
        command = NightlyCommand(start_date, release_tag)

    if args.telemetry:
        logger.info("Activating Rally telemetry %s." % args.telemetry)
        command = TelemetryDecorator(command, args.telemetry, args.telemetry_params)

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
