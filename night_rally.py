import argparse
import datetime
import errno
import fileinput
import logging
import os
import shutil
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


def date_for_path(d):
    # This relies on the fact that Rally uses the same pattern...
    return "{:%Y-%m-%d-%H-%M-%S}".format(d)


def to_iso8601(d):
    """
    Convert a datetime instance to a ISO-8601 compliant string.
    :param d: A datetime instance (assuming timezone UTC)
    :return: The corresponding ISO-8601 formatted string
    """
    return "{:%Y-%m-%dT%H:%M:%SZ}".format(d)


def to_iso8601_short(d):
    return "{:%Y%m%dT%H%M%SZ}".format(d)


def ensure_dir(directory):
    """
    Ensure that the provided directory and all of its parent directories exist.
    This function is safe to execute on existing directories (no op).

    :param directory: The directory to create (if it does not exist).
    """
    try:
        # avoid a race condition by trying to create the checkout directory
        os.makedirs(directory)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def sanitize(text):
    """
    Sanitizes the input text so it is safe to use as an environment name in Rally.

    :param text: A text to sanitize
    """
    return text.lower().replace(" ", "-").replace(".", "_")


def configure_rally(configuration_name, dry_run):
    user_home = os.getenv("HOME")
    source = "%s/resources/rally-template.ini" % ROOT
    destination = "%s/.rally/rally-%s.ini" % (user_home, configuration_name)
    logger.info("Copying rally configuration from [%s] to [%s]" % (source, destination))
    if not dry_run:
        ensure_dir("%s/.rally" % user_home)
        shutil.copyfile(source, destination)
        # materialize current user home and set environment name
        with fileinput.input(files=destination, inplace=True) as f:
            for line in f:
                print(line
                      .replace("~", user_home)
                      .replace("<<ENVIRONMENT>>", configuration_name))


class BaseCommand:
    def __init__(self, effective_start_date, target_host, root_dir):
        self.effective_start_date = effective_start_date
        self.target_host = target_host
        self.root_dir = root_dir
        self.ts = date_for_cmd_param(effective_start_date)

    def report_path(self, track, challenge, car):
        return "%s/reports/rally/%s/%s/%s/%s/report.csv" % (self.root_dir, date_for_path(self.effective_start_date), track, challenge, car)

    def runnable(self, track, challenge, car):
        return True

    def command_line(self, track, challenge, car):
        raise NotImplementedError("abstract method")


class SourceBasedCommand(BaseCommand):
    def __init__(self, effective_start_date, target_host, root_dir, revision, configuration_name, user_tag=None, override_src_dir=None):
        super().__init__(effective_start_date, target_host, root_dir)
        self.revision = revision
        self.configuration_name = configuration_name
        self.pipeline = "from-sources-complete"
        if override_src_dir is not None:
            self.override = " --override-src-dir=%s" % override_src_dir
        else:
            self.override = ""
        if user_tag:
            self.user_tag = " --user-tag=\"intention:%s\"" % user_tag
        else:
            self.user_tag = ""

    def command_line(self, track, challenge, car):
        cmd = "{11} --configuration-name={9} --target-host={8} --pipeline={6} --quiet --revision \"{0}\" " \
              "--effective-start-date \"{1}\" --track={2} --challenge={3} --car={4} --report-format=csv --report-file={5}{7}{10}". \
            format(self.revision, self.ts, track, challenge, car, self.report_path(track, challenge, car), self.pipeline, self.override,
                   self.target_host, self.configuration_name, self.user_tag, RALLY_BINARY)
        # after we've executed the first benchmark, there is no reason to build again from sources
        self.pipeline = "from-sources-skip-build"
        return cmd


class NightlyCommand(SourceBasedCommand):
    CONFIG_NAME = "nightly"

    def __init__(self, effective_start_date, target_host, root_dir, override_src_dir=None):
        super().__init__(effective_start_date, target_host, root_dir, "@%s" % to_iso8601(effective_start_date),
                         NightlyCommand.CONFIG_NAME, user_tag=None, override_src_dir=override_src_dir)


class AdHocCommand(SourceBasedCommand):
    def __init__(self, revision, effective_start_date, target_host, root_dir, configuration_name, user_tag, override_src_dir=None):
        super().__init__(effective_start_date, target_host, root_dir, revision, configuration_name, user_tag, override_src_dir)


class ReleaseCommand(BaseCommand):
    def __init__(self, effective_start_date, target_host, plugins, root_dir, distribution_version, configuration_name, tag):
        super().__init__(effective_start_date, target_host, root_dir)
        self.plugins = plugins
        self.configuration_name = configuration_name
        self.pipeline = "from-distribution"
        self.distribution_version = distribution_version
        self._tag = tag

    def runnable(self, track, challenge, car):
        # Do not run 1g benchmarks at all at the moment. Earlier versions of ES OOM.
        if car == "1gheap":
            return False
        # cannot run "sorted" challenges - it's a 6.0+ feature
        if int(self.distribution_version[0]) < 6:
            return "sorted" not in challenge
        return True

    def command_line(self, track, challenge, car):
        cmd = "{10} --configuration-name={8} --target-host={7} --pipeline={6} --quiet --distribution-version={0} " \
              "--effective-start-date \"{1}\" --track={2} --challenge={3} --car={4} --report-format=csv --report-file={5} " \
              "--user-tag=\"{9}\"".format(self.distribution_version, self.ts, track, challenge, car,
                                          self.report_path(track, challenge, car), self.pipeline,
                                          self.target_host, self.configuration_name, self.tag(), RALLY_BINARY)
        if self.plugins:
            cmd += " --elasticsearch-plugins=\"%s\"" % self.plugins
            if "x-pack:security" in self.plugins:
                cmd += " --cluster-health=yellow " \
                       "--client-options=\"use_ssl:true,verify_certs:false,basic_auth_user:'rally',basic_auth_password:'rally-password'\""

        return cmd

    def tag(self):
        return self._tag


class DockerCommand(BaseCommand):
    def __init__(self, effective_start_date, target_host, root_dir, distribution_version, configuration_name):
        super().__init__(effective_start_date, target_host, root_dir)
        self.configuration_name = configuration_name
        self.pipeline = "docker"
        self.distribution_version = distribution_version

    def runnable(self, track, challenge, car):
        if car in ["two_nodes", "verbose_iw", "1gheap"]:
            return False
        # cannot run "sorted" challenges - it's a 6.0+ feature
        if int(self.distribution_version[0]) < 6:
            return "sorted" not in challenge
        return True

    def command_line(self, track, challenge, car):
        cmd = "{10} --configuration-name={8} --target-host={7} --pipeline={6} --quiet --distribution-version={0} " \
              "--effective-start-date \"{1}\" --track={2} --challenge={3} --car={4} --report-format=csv --report-file={5} " \
              "--cluster-health=yellow --user-tag=\"{9}\"". \
            format(self.distribution_version, self.ts, track, challenge, car, self.report_path(track, challenge, car), self.pipeline,
                   self.target_host, self.configuration_name, self.tag(), RALLY_BINARY)
        return cmd

    @staticmethod
    def tag():
        return "env:docker"


def run_rally(tracks, command, dry_run=False, system=os.system):
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
            if command.runnable(track_name, challenge, car):
                logger.info("Running Rally on track [%s] with challenge [%s] and car [%s]" % (track_name, challenge, car))
                start = time.perf_counter()
                if runner(command.command_line(track_name, challenge, car)):
                    rally_failure = True
                    logger.error("Failed to run track [%s]. Please check the logs." % track_name)
                stop = time.perf_counter()
                logger.info("Finished running on track [%s] with challenge [%s] and car [%s] in [%f] seconds." % (
                    track_name, challenge, car, (stop - start)))
            else:
                logger.info("Skipping track [%s], challenge [%s] and car [%s] (not supported by command)." % (track_name, challenge, car))
    return rally_failure


#################################################
# Reporting
#################################################

def copy_results_for_release_comparison(effective_start_date, dry_run, tag):
    if not dry_run:
        import client
        import elasticsearch.helpers
        """
        Copies all results in the metric store for the given trial timestamp so that they are also available as master release results.
        """
        es = client.create_client()
        es.indices.refresh(index="rally-results-*")
        ts = to_iso8601_short(effective_start_date)
        query = {
            "query": {
                "term": {
                    "trial-timestamp": ts
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
            src["user-tag"] = tag
            release_results.append(src)
        if release_results:
            logger.info("Copying %d result documents for [%s] to release environment." % (len(release_results), ts))
            elasticsearch.helpers.bulk(es, release_results, index=index, doc_type=doc_type)


def deactivate_outdated_results(effective_start_date, environment, release, tag, dry_run):
    """
    Sets all results for the same major release version, environment and tag to active=False except for the records with the provided 
    effective start date.
    """
    ts = to_iso8601_short(effective_start_date)
    logger.info("Activating results only for [%s] on [%s] in environment [%s] and tag [%s]." % (release, ts, environment, tag))
    body = {
        "script": {
            "inline": "ctx._source.active = false",
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

    if tag:
        body["query"]["bool"]["filter"].append({
            "term": {
                "user-tag": tag
            }
        })
    if dry_run:
        import json
        logger.info("Would execute update query script\n%s" % json.dumps(body, indent=2))
    else:
        import client
        es = client.create_client()
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
        "--override-src-dir",
        help=argparse.SUPPRESS,
        default=None)
    parser.add_argument(
        "--tag",
        help=argparse.SUPPRESS,
        default=None)
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

    return parser.parse_args()


def load_tracks():
    import json
    with open("%s/resources/tracks.json" % ROOT, "r") as tracks_file:
        return json.load(tracks_file)


def main():
    args = parse_args()

    release_mode = args.mode == "release"
    adhoc_mode = args.mode == "adhoc"
    nightly_mode = args.mode == "nightly"

    plugins = args.elasticsearch_plugins

    tag = args.tag
    if "encryption-at-rest" in args.fixtures:
        release_tag = "env:ear"
    elif "x-pack:security" in plugins:
        release_tag = "env:x-pack"
    else:
        release_tag = "env:bare"
    docker_benchmark = args.release.startswith("Docker ")
    release = args.release.replace("Docker ", "")

    tracks = load_tracks()
    root_dir = "%s/.rally/benchmarks" % os.getenv("HOME")

    if release_mode:
        # use always the same name for release comparison benchmarks
        env_name = sanitize(args.mode)
        if docker_benchmark:
            if plugins:
                raise RuntimeError("User specified plugins [%s] but this is not supported for Docker benchmarks." % plugins)
            logger.info("Running Docker release benchmarks for release [%s] against [%s]." % (release, args.target_host))
            command = DockerCommand(args.effective_start_date, args.target_host, root_dir, release, env_name)
            tag = command.tag()
        else:
            logger.info("Running release benchmarks for release [%s] against [%s] (release tag is [%s])."
                        % (release, args.target_host, release_tag))
            command = ReleaseCommand(args.effective_start_date, args.target_host, plugins, root_dir, release, env_name, release_tag)
            tag = command.tag()
    elif adhoc_mode:
        if plugins:
            raise RuntimeError("User specified plugins [%s] but this is not supported for adhoc benchmarks." % plugins)
        logger.info("Running adhoc benchmarks for revision [%s] against [%s]." % (args.revision, args.target_host))
        # copy data from templates directory to our dedicated output directory
        env_name = sanitize(args.release)
        command = AdHocCommand(args.revision, args.effective_start_date, args.target_host, root_dir, env_name, args.tag, args.override_src_dir)
    else:
        if plugins:
            raise RuntimeError("User specified plugins [%s] but this is not supported for nightly benchmarks." % plugins)
        logger.info("Running nightly benchmarks against [%s]." % args.target_host)
        env_name = NightlyCommand.CONFIG_NAME
        command = NightlyCommand(args.effective_start_date, args.target_host, root_dir, args.override_src_dir)

    configure_rally(env_name, args.dry_run)
    rally_failure = run_rally(tracks, command, args.dry_run)

    if nightly_mode:
        copy_results_for_release_comparison(args.effective_start_date, args.dry_run, release_tag)
        # we want to deactivate old release entries, not old nightly entries
        deactivate_outdated_results(args.effective_start_date, "release", release, release_tag, args.dry_run)
    else:
        deactivate_outdated_results(args.effective_start_date, env_name, release, tag, args.dry_run)
    if rally_failure:
        exit(1)


if __name__ == "__main__":
    main()
