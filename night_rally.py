import argparse
import collections
import csv
import datetime
import errno
import fileinput
import logging
import os
import re
import shutil
import time

tracks = collections.OrderedDict()

tracks["nested"] = [
    ["nested-search-challenge", "4gheap"],
    ["nested-search-challenge", "1gheap"]
]

tracks["geonames"] = [
    ["append-no-conflicts", "defaults"],
    ["append-no-conflicts-index-only", "4gheap"],
    ["append-sorted-no-conflicts", "4gheap"],
    ["append-fast-with-conflicts", "4gheap"],
    ["append-no-conflicts-index-only-1-replica", "two_nodes"],
    ["append-no-conflicts-index-only", "verbose_iw"],
    ["append-no-conflicts", "1gheap"],
]

tracks["percolator"] = [
    ["append-no-conflicts", "4gheap"],
    ["append-no-conflicts", "1gheap"]
]

tracks["geopoint"] = [
    ["append-no-conflicts", "defaults"],
    ["append-no-conflicts-index-only", "4gheap"],
    ["append-fast-with-conflicts", "4gheap"],
    ["append-no-conflicts-index-only-1-replica", "two_nodes"],
    ["append-no-conflicts", "1gheap"],
]

tracks["pmc"] = [
    ["append-no-conflicts-index-only", "defaults"],
    ["append-no-conflicts", "4gheap"],
    ["append-sorted-no-conflicts", "4gheap"],
    ["append-fast-with-conflicts", "4gheap"],
    ["append-no-conflicts-index-only-1-replica", "two_nodes"],
    ["append-no-conflicts", "1gheap"],
]

tracks["nyc_taxis"] = [
    ["append-no-conflicts", "4gheap"],
    ["append-sorted-no-conflicts-index-only", "4gheap"],
    ["append-no-conflicts", "1gheap"],
]

tracks["logging"] = [
    ["append-no-conflicts-index-only", "defaults"],
    ["append-no-conflicts", "4gheap"],
    ["append-sorted-no-conflicts", "4gheap"],
    ["append-no-conflicts", "1gheap"],
]

tracks["noaa"] = [
    ["append-no-conflicts", "defaults"],
]

# default challenge / car per track
defaults = {
    "geonames": ("append-no-conflicts", "defaults"),
    "percolator": ("append-no-conflicts", "4gheap"),
    "geopoint": ("append-no-conflicts", "defaults"),
    "pmc": ("append-no-conflicts", "4gheap"),
    "nyc_taxis": ("append-no-conflicts", "4gheap"),
    "nested": ("nested-search-challenge", "4gheap"),
    "logging": ("append-no-conflicts", "4gheap"),
    "noaa": ("append-no-conflicts", "defaults"),
}

config = {
    "root.dir": "%s/.rally/benchmarks" % os.getenv("HOME"),
    "report.base.dir": "reports"
}

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
    root = os.path.dirname(os.path.realpath(__file__))
    source = "%s/resources/rally-template.ini" % root
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
        self.report_root_dir = config["report.base.dir"]

    def report_path(self, track, challenge, car):
        return "%s/%s/rally/%s/%s/%s/%s/report.csv" % (self.root_dir, self.report_root_dir,
                                                       date_for_path(self.effective_start_date), track,
                                                       challenge, car)

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

    def runnable(self, track, challenge, car):
        # Run 1gb benchmarks  only every other day
        return car != "1gheap" or self.effective_start_date.day % 2 == 1


class AdHocCommand(SourceBasedCommand):
    def __init__(self, revision, effective_start_date, target_host, root_dir, configuration_name, user_tag, override_src_dir=None):
        super().__init__(effective_start_date, target_host, root_dir, revision, configuration_name, user_tag, override_src_dir)


class ReleaseCommand(BaseCommand):
    def __init__(self, effective_start_date, target_host, root_dir, distribution_version, configuration_name, tag):
        super().__init__(effective_start_date, target_host, root_dir)
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
        return cmd

    def tag(self):
        return self._tag


class DockerCommand(BaseCommand):
    def __init__(self, effective_start_date, target_host, root_dir, distribution_version, configuration_name):
        super().__init__(effective_start_date, target_host, root_dir)
        self.configuration_name = configuration_name
        self.pipeline = "docker"
        self.distribution_version = distribution_version.replace("Docker ", "")

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
    for track, setups in tracks.items():
        for setup in setups:
            challenge, car = setup
            if command.runnable(track, challenge, car):
                logger.info("Running Rally on track [%s] with challenge [%s] and car [%s]" % (track, challenge, car))
                start = time.perf_counter()
                if runner(command.command_line(track, challenge, car)):
                    rally_failure = True
                    logger.error("Failed to run track [%s]. Please check the logs." % track)
                stop = time.perf_counter()
                logger.info("Finished running on track [%s] with challenge [%s] and car [%s] in [%f] seconds." % (
                    track, challenge, car, (stop - start)))
            else:
                logger.info("Skipping track [%s], challenge [%s] and car [%s] (not supported by command)." % (track, challenge, car))
    return rally_failure


def v(d, k):
    try:
        return d[k]
    except KeyError:
        return ""


#################################################
# Reporting
#################################################

METRICS_TO_KEY = {
    "Median Throughput": "median_indexing_throughput",
    "Total Young Gen GC": "young_gen_gc",
    "Total Old Gen GC": "old_gen_gc",
    "Indexing time": "indexing_time",
    "Refresh time": "refresh_time",
    "Flush time": "flush_time",
    "Merge time": "merge_time",
    "Merge throttle time": "merge_throttle_time",
    "Segment count": "segment_count",
    "Index size": "index_size",
    "Totally written": "totally_written",
    "Heap used for segments.*": "mem_segments",
    "Heap used for doc values.*": "mem_doc_values",
    "Heap used for terms": "mem_terms",
    "Heap used for norms": "mem_norms",
    "Heap used for points": "mem_points",
    "Heap used for stored fields": "mem_fields",
    "99(\.0)?th percentile service time": "query_latency_p99",
    "Merge time \(.*": "merge_time_parts"
}

META_METRICS_TO_KEY = {
    "Elasticsearch source revision": "source_revision"
}


def is_default_setup(default_setup, current_setup):
    current_challenge, current_car = current_setup
    default_challenge, default_car = default_setup

    return current_challenge == default_challenge and current_car == default_car


def is_multi_valued(metric_key):
    return metric_key in ["query_latency_p99", "merge_time_parts"]


def is_indexing_operation(op_name):
    return op_name.startswith("index") and not op_name.endswith("stats")


def key_for(metric_pattern, metric_key, metric_name, op_name):
    # force full regex match
    if re.match("^%s$" % metric_pattern, metric_name):
        if metric_key == "median_indexing_throughput":
            if is_indexing_operation(op_name):
                return metric_key
            else:
                return None
        elif metric_key == "query_latency_p99":
            if op_name == "index-stats":
                return "latency_indices_stats_p99"
            elif op_name == "node-stats":
                return "latency_nodes_stats_p99"
            elif is_indexing_operation(op_name) or op_name == "force-merge":
                return None
        return metric_key
    return None


def meta_key_for(metric_pattern, metric_key, metric_name):
    if re.match(metric_pattern, metric_name):
        return metric_key
    return None


def extract_metrics(source_report):
    metrics = {}
    for row in csv.reader(source_report):
        lap = row[0]
        # Don't consider any metrics except the final one
        if lap == "All":
            for metric_pattern, metric_key in METRICS_TO_KEY.items():
                metric_name = row[1]
                op_name = row[2]
                metric_value = row[3]

                final_key = key_for(metric_pattern, metric_key, metric_name, op_name)
                if final_key:
                    if is_multi_valued(final_key):
                        if final_key not in metrics:
                            metrics[final_key] = []
                        metrics[final_key].append(metric_value)
                    else:
                        metrics[final_key] = metric_value
    return metrics


def extract_meta_metrics(source_meta_report):
    meta_metrics = {}
    for row in csv.reader(source_meta_report):
        for metric_pattern, metric_key in META_METRICS_TO_KEY.items():
            metric_name = row[0]
            metric_value = row[1]
            final_key = meta_key_for(metric_pattern, metric_key, metric_name)
            if final_key:
                if is_multi_valued(final_key):
                    if final_key not in meta_metrics:
                        meta_metrics[final_key] = []
                    meta_metrics[final_key].append(metric_value)
                else:
                    meta_metrics[final_key] = metric_value
    return meta_metrics


def insert(lines, replace_release, new_release_name, data):
    new_lines = []
    found = False
    for line in lines:
        if line.startswith(replace_release):
            new_lines.append("%s,%s" % (new_release_name, data))
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append("%s,%s" % (new_release_name, data))
    return new_lines


class MetricReader:
    def __init__(self, effective_start_date, root_dir):
        self.timestamp = date_for_path(effective_start_date)
        self.root_dir = root_dir
        self.report_root_dir = config["report.base.dir"]

    def metrics(self, track, challenge, car):
        report_path = "%s/%s/rally/%s/%s/%s/%s/report.csv" % (self.root_dir, self.report_root_dir, self.timestamp, track, challenge, car)
        if not os.path.isfile(report_path):
            logger.warn("[%s] does not exist. Skipping track [%s], challenge [%s], car [%s]."
                        % (report_path, track, challenge, car))
            return None

        with open(report_path) as csvfile:
            return extract_metrics(csvfile)

    def meta_metrics(self, track, challenge, car):
        meta_report_path = "%s/%s/rally/%s/%s/%s/%s/report.csv.meta" % (self.root_dir, self.report_root_dir, self.timestamp, track, challenge, car)
        if not os.path.isfile(meta_report_path):
            logger.warn("Could not find [%s]. No git meta-data will be available for this trial run." % meta_report_path)
            return None

        with open(meta_report_path) as csvfile:
            return extract_meta_metrics(csvfile)


class Reporter:
    def __init__(self, root_dir, effective_start_date, adhoc_mode, compare_mode, dry_run, replace_release, release_name):
        self.report_timestamp = date_for_cmd_param(effective_start_date)
        self.report_root_dir = config["report.base.dir"]
        self.root_dir = root_dir
        self.adhoc_mode = adhoc_mode
        self.compare_mode = compare_mode
        self.dry_run = dry_run
        self.replace_release = replace_release
        self.release_name = release_name
        self.adhoc_template_root_path = "%s/%s/templates" % (self.root_dir, self.report_root_dir)
        if self.adhoc_mode:
            self.output_root_path = "%s/%s/out/%s" % (self.root_dir, self.report_root_dir, sanitize(self.release_name))
        else:
            self.output_root_path = "%s/%s/out" % (self.root_dir, self.report_root_dir)

    def __call__(self, track, report_name, data):
        formatted_data = "%s\n" % ",".join(data)
        p = self._output_report_path(track)
        if not self.compare_mode:
            self._write_report("%s/%s.csv" % (p, report_name), formatted_data)
        output_path = "%s/%s_comparison.csv" % (p, report_name)
        # noinspection PyBroadException
        try:
            self._insert_comparison_data(output_path, formatted_data)
        except BaseException:
            logger.exception("Failed to write comparison data to [%s]." % output_path)

        # write the comparison data again for our adhoc benchmark templates. master is always considered our baseline for adhoc benchmarks.
        # We could support arbitrary baselines but the problem is the graphing library that is pretty picky about the data in the source
        # CSV file and that's why we limit ourselves to master as a baseline for the moment.
        if self.release_name == "master":
            adhoc_path = self._adhoc_template_path(track)
            logger.info("Writing comparison data for [%s] also to template directory [%s]." % (self.release_name, adhoc_path))
            # noinspection PyBroadException
            try:
                self._insert_comparison_data("%s/%s_comparison.csv" % (adhoc_path, report_name), formatted_data)
            except BaseException:
                logger.exception("Failed to write comparison data for [%s] to template directory [%s]." % (self.release_name, adhoc_path))

    def copy_template(self):
        # prevent stupid mistakes
        if self.adhoc_mode:
            logger.info("Copying most recent templates from [%s] to [%s]." % (self.adhoc_template_root_path, self.output_root_path))
            if not self.dry_run:
                # ensure that the target directory does NOT exist
                shutil.rmtree(self.output_root_path, ignore_errors=True)
                shutil.copytree(self.adhoc_template_root_path, self.output_root_path)

    def write_meta_report(self, track, revision):
        if not self.compare_mode:
            with open("%s/source_revision.csv" % self._output_report_path(track), "a") as f:
                f.write("%s,%s\n" % (self.report_timestamp, revision))

    def _output_report_path(self, track):
            return "%s/%s" % (self.output_root_path, track)

    def _adhoc_template_path(self, track):
        return "%s/%s" % (self.adhoc_template_root_path, track)

    def _write_report(self, file_name, data):
        with open(file_name, "a") as of:
            of.write("%s,%s" % (self.report_timestamp, data))

    def _insert_comparison_data(self, file_name, data):
        # in ad-hoc mode we're bound to a constant name due graphing library constraints (it cannot get the data series name from the CSV)
        series_name = "Adhoc" if self.adhoc_mode else self.release_name
        with open(file_name, "r+") as f:
            lines = f.readlines()
            new_lines = insert(lines, self.replace_release, series_name, data)
            f.seek(0)
            f.writelines(new_lines)
            f.truncate()


def report(tracks, default_setup_per_track, reader, reporter):
    """
    Publishes all data from the provided trial run.

    :param tracks: A hash of all tracks that have been run and their challenges.
    :param default_setup_per_track: A hash of the default challenge / car per track.
    :param reader: A ``Reader`` instance that can read the race results.
    :param reporter: A ``Reporter`` instance that can write the result files.

    """

    for track, setups in tracks.items():
        segment_count_metrics = []
        indexing_throughput_metrics = []
        meta_metrics = None
        for setup in setups:
            challenge, car = setup
            current_is_default = is_default_setup(default_setup_per_track[track], setup)

            metrics = reader.metrics(track, challenge, car)
            if not metrics:
                continue
            meta_metrics = reader.meta_metrics(track, challenge, car)

            # "verbose_iw" is just a tool to get the merge time parts stats. We actually do not care about segment counts and the indexing
            # throughput in this case. So we'll just skip it.
            if car != "verbose_iw":
                # Beware: this one is one column per series!
                segment_count_metrics.append(metrics.get("segment_count", ""))
                indexing_throughput_metrics.append(metrics.get("median_indexing_throughput", ""))

            if "merge_time_parts" in metrics:
                reporter(track, "merge_parts", metrics["merge_time_parts"])

            if current_is_default:
                if "cpu_usage" in metrics:
                    reporter(track, "indexing_cpu_usage", [metrics["cpu_usage"]])

                if "young_gen_gc" in metrics or "old_gen_gc" in metrics:
                    reporter(track, "gc_times", [v(metrics, "young_gen_gc"), v(metrics, "old_gen_gc")])

                if "latency_indices_stats_p99" in metrics or "latency_nodes_stats_p99" in metrics:
                    reporter(track, "search_latency_stats", [v(metrics, "latency_indices_stats_p99"), v(metrics, "latency_nodes_stats_p99")])

                if "mem_segments" in metrics:
                    # Date,Total heap used (MB),Doc values (MB),Terms (MB),Norms (MB),Stored fields (MB),Points (MB)
                    total_memory = [v(metrics, "mem_segments"),
                                    v(metrics, "mem_doc_values"),
                                    v(metrics, "mem_terms"),
                                    v(metrics, "mem_norms"),
                                    v(metrics, "mem_fields"),
                                    v(metrics, "mem_points")]
                    reporter(track, "segment_total_memory", total_memory)

                if "indexing_time" in metrics:
                    # Date,Indexing time (min),Merge time (min),Refresh time (min),Flush time (min),Merge throttle time (min)
                    total_times = [v(metrics, "indexing_time"),
                                   v(metrics, "merge_time"),
                                   v(metrics, "refresh_time"),
                                   v(metrics, "flush_time"),
                                   v(metrics, "merge_throttle_time")]
                    reporter(track, "indexing_total_times", total_times)

                if "index_size" in metrics or "totally_written" in metrics:
                    # Date,Final index size,Total bytes written
                    reporter(track, "disk_usage", [v(metrics, "index_size"), v(metrics, "totally_written")])

                if "query_latency_p99" in metrics:
                    reporter(track, "search_latency_queries", metrics["query_latency_p99"])

        if len(segment_count_metrics) > 0:
            reporter(track, "segment_counts", segment_count_metrics)

        if len(indexing_throughput_metrics) > 0:
            reporter(track, "indexing_throughput", indexing_throughput_metrics)

        if meta_metrics and "source_revision" in meta_metrics:
            reporter.write_meta_report(track, meta_metrics["source_revision"])


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
    import client
    ts = to_iso8601_short(effective_start_date)
    logger.info("Activating results only for [%s] on [%s] in environment [%s]." % (release, ts, environment))
    if not dry_run:
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
        "--override-root-dir",
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
    # Deprecated
    parser.add_argument(
        "--replace-release",
        help="Specify the release string to replace for comparison reports")

    return parser.parse_args()


def main():
    args = parse_args()
    release_mode = args.mode == "release"
    adhoc_mode = args.mode == "adhoc"
    nightly_mode = args.mode == "nightly"
    root_dir = config["root.dir"] if not args.override_root_dir else args.override_root_dir
    tag = args.tag
    release_tag = "env:ear" if "encryption-at-rest" in args.fixtures else "env:bare"

    if release_mode:
        # use always the same name for release comparison benchmarks
        env_name = sanitize(args.mode)
        if args.release.startswith("Docker"):
            logger.info("Running Docker release benchmarks for release [%s] against [%s]." % (args.release, args.target_host))
            command = DockerCommand(args.effective_start_date, args.target_host, root_dir, args.release, env_name)
            tag = command.tag()
        else:
            logger.info("Running release benchmarks for release [%s] against [%s] (release tag is [%s])."
                        % (args.release, args.target_host, release_tag))
            command = ReleaseCommand(args.effective_start_date, args.target_host, root_dir, args.release, env_name, release_tag)
            tag = command.tag()
    elif adhoc_mode:
        logger.info("Running adhoc benchmarks for revision [%s] against [%s]." % (args.revision, args.target_host))
        # copy data from templates directory to our dedicated output directory
        env_name = sanitize(args.release)
        command = AdHocCommand(args.revision, args.effective_start_date, args.target_host, root_dir, env_name, args.tag, args.override_src_dir)
    else:
        logger.info("Running nightly benchmarks against [%s]." % args.target_host)
        env_name = NightlyCommand.CONFIG_NAME
        command = NightlyCommand(args.effective_start_date, args.target_host, root_dir, args.override_src_dir)

    configure_rally(env_name, args.dry_run)
    rally_failure = run_rally(tracks, command, args.dry_run)
    # TODO dm: Remove this for new Kibana-based charts - we use a different logic there (only one series per major release and tag).
    replace_release = args.replace_release if args.replace_release else args.release

    if nightly_mode:
        copy_results_for_release_comparison(args.effective_start_date, args.dry_run, release_tag)
        # we want to deactivate old release entries, not old nightly entries
        deactivate_outdated_results(args.effective_start_date, "release", args.release, tag, args.dry_run)
    else:
        deactivate_outdated_results(args.effective_start_date, env_name, args.release, tag, args.dry_run)
    # TODO dm: Remove this for new Kibana-based charts
    reader = MetricReader(args.effective_start_date, root_dir)
    reporter = Reporter(root_dir, args.effective_start_date, adhoc_mode, release_mode, args.dry_run, replace_release, args.release)
    reporter.copy_template()
    report(tracks, defaults, reader, reporter)
    if rally_failure:
        exit(1)


if __name__ == "__main__":
    main()
