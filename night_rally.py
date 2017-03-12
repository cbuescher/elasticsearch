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
    ["nested-search-challenge", "4gheap"]
]

tracks["geonames"] = [
    ["append-no-conflicts", "defaults"],
    ["append-no-conflicts-index-only", "4gheap"],
    ["append-fast-no-conflicts", "4gheap"],
    ["append-fast-with-conflicts", "4gheap"],
    ["append-no-conflicts-index-only-1-replica", "two_nodes"],
    ["append-no-conflicts-index-only", "verbose_iw"]
]

tracks["percolator"] = [
    ["append-no-conflicts", "4gheap"]
]

tracks["geopoint"] = [
    ["append-no-conflicts", "defaults"],
    ["append-no-conflicts-index-only", "4gheap"],
    ["append-fast-no-conflicts", "4gheap"],
    ["append-fast-with-conflicts", "4gheap"],
    ["append-no-conflicts-index-only-1-replica", "two_nodes"]
]

tracks["pmc"] = [
    ["append-no-conflicts", "defaults"],
    ["append-no-conflicts", "4gheap"],
    ["append-fast-no-conflicts", "4gheap"],
    ["append-fast-with-conflicts", "4gheap"],
    ["append-no-conflicts-index-only-1-replica", "two_nodes"]
]

tracks["nyc_taxis"] = [
    ["append-no-conflicts", "4gheap"]
]

# default challenge / car per track
defaults = {
    "geonames": ("append-no-conflicts", "defaults"),
    "percolator": ("append-no-conflicts", "4gheap"),
    "geopoint": ("append-no-conflicts", "defaults"),
    "pmc": ("append-no-conflicts", "4gheap"),
    "nyc_taxis": ("append-no-conflicts", "4gheap"),
    "nested": ("nested-search-challenge", "4gheap"),
}

config = {
    "root.dir": "%s/.rally/benchmarks" % os.getenv("HOME"),
    "report.base.dir": "reports"
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


def configure_rally(dry_run):
    user_home = os.getenv("HOME")
    root = os.path.dirname(os.path.realpath(__file__))
    source = "%s/resources/rally-nightly.ini" % root
    destination = "%s/.rally/rally-nightly.ini" % user_home
    logger.info("Copying rally configuration from [%s] to [%s]" % (source, destination))
    if not dry_run:
        ensure_dir("%s/.rally" % user_home)
        shutil.copyfile(source, destination)
        # materialize current user home
        with fileinput.input(files=destination, inplace=True) as f:
            for line in f:
                print(line.replace("~", user_home))


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


class NightlyCommand(BaseCommand):
    def __init__(self, effective_start_date, target_host, root_dir, override_src_dir=None):
        super().__init__(effective_start_date, target_host, root_dir)
        self.revision_ts = to_iso8601(effective_start_date)
        self.pipeline = "from-sources-complete"
        if override_src_dir is not None:
            self.override = " --override-src-dir=%s" % override_src_dir
        else:
            self.override = ""

    def command_line(self, track, challenge, car):
        cmd = "rally --configuration-name=nightly --target-host={8} --pipeline={6} --quiet --revision \"@{0}\" " \
              "--effective-start-date \"{1}\" --track={2} --challenge={3} --car={4} --report-format=csv --report-file={5}{7}". \
            format(self.revision_ts, self.ts, track, challenge, car, self.report_path(track, challenge, car), self.pipeline, self.override,
                   self.target_host)
        # after we've executed the first benchmark, there is no reason to build again from sources
        self.pipeline = "from-sources-skip-build"
        return cmd


class ReleaseCommand(BaseCommand):
    def __init__(self, effective_start_date, target_host, root_dir, distribution_version):
        super().__init__(effective_start_date, target_host, root_dir)
        self.pipeline = "from-distribution"
        self.distribution_version = distribution_version

    def command_line(self, track, challenge, car):
        cmd = "rally --target-host={7} --pipeline={6} --quiet --distribution-version={0} --effective-start-date \"{1}\" " \
              "--track={2} --challenge={3} --car={4} --report-format=csv --report-file={5}". \
            format(self.distribution_version, self.ts, track, challenge, car, self.report_path(track, challenge, car), self.pipeline,
                   self.target_host)
        return cmd


class DockerCommand(BaseCommand):
    def __init__(self, effective_start_date, target_host, root_dir, distribution_version):
        super().__init__(effective_start_date, target_host, root_dir)
        self.pipeline = "docker"
        self.distribution_version = distribution_version.replace("Docker ", "")

    def runnable(self, track, challenge, car):
        return car not in ["two_nodes", "verbose_iw"]

    def command_line(self, track, challenge, car):
        cmd = "rally --target-host={7} --pipeline={6} --quiet --distribution-version={0} --effective-start-date \"{1}\" " \
              "--track={2} --challenge={3} --car={4} --report-format=csv --report-file={5} --cluster-health=yellow " \
              "--client-options=\"basic_auth_user:'elastic',basic_auth_password:'changeme',timeout:60000,request_timeout:60000\"". \
            format(self.distribution_version, self.ts, track, challenge, car, self.report_path(track, challenge, car), self.pipeline,
                   self.target_host)
        return cmd


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
    "99.0th percentile service time": "query_latency_p99",
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


def write_report(file_name, timestamp, data):
    with open(file_name, "a") as f:
        f.write("%s,%s" % (timestamp, data))


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


def insert_comparison_data(file_name, data, replace_release, new_release_name):
    with open(file_name, "r+") as f:
        lines = f.readlines()
        new_lines = insert(lines, replace_release, new_release_name, data)
        f.seek(0)
        f.writelines(new_lines)
        f.truncate()


def report(effective_start_date, tracks, default_setup_per_track, replace_release, release_name, root_dir, compare_mode):
    """
    Publishes all data from the provided trial run.

    :param effective_start_date: A timestamp for which we should publish data.
    :param tracks: A hash of all tracks that have been run and their challenges.
    :param default_setup_per_track: A hash of the default challenge / car per track.

    """
    timestamp = date_for_path(effective_start_date)
    # this timestamp gets used in the report files
    report_timestamp = date_for_cmd_param(effective_start_date)
    report_root_dir = config["report.base.dir"]

    for track, setups in tracks.items():
        output_report_path = "%s/%s/out/%s" % (root_dir, report_root_dir, track)
        segment_count_metrics = []
        indexing_throughput_metrics = []
        meta_metrics = None

        for setup in setups:
            challenge, car = setup
            current_is_default = is_default_setup(default_setup_per_track[track], setup)
            report_path = "%s/%s/rally/%s/%s/%s/%s/report.csv" % (root_dir, report_root_dir, timestamp, track, challenge, car)
            meta_report_path = "%s/%s/rally/%s/%s/%s/%s/report.csv.meta" % (root_dir, report_root_dir, timestamp, track, challenge, car)

            if not os.path.isfile(report_path):
                logger.warn("[%s] does not exist. Skipping track [%s], challenge [%s], car [%s]."
                            % (report_path, track, challenge, car))
                continue

            with open(report_path) as csvfile:
                metrics = extract_metrics(csvfile)

            if "segment_count" in metrics:
                segment_count_metrics.append(metrics["segment_count"])
            else:
                segment_count_metrics.append("")

            # Beware: this one is one column per series!
            if "median_indexing_throughput" in metrics:
                indexing_throughput_metrics.append(metrics["median_indexing_throughput"])
            else:
                indexing_throughput_metrics.append("")

            if current_is_default and "cpu_usage" in metrics:
                cpu_usage = "%s\n" % metrics["cpu_usage"]
                if not compare_mode:
                    write_report("%s/indexing_cpu_usage.csv" % output_report_path, report_timestamp, cpu_usage)
                insert_comparison_data("%s/indexing_cpu_usage_comparison.csv" % output_report_path, cpu_usage, replace_release, release_name)

            if current_is_default and ("young_gen_gc" in metrics or "old_gen_gc" in metrics):
                gc_times = "%s,%s\n" % (v(metrics, "young_gen_gc"), v(metrics, "old_gen_gc"))
                if not compare_mode:
                    write_report("%s/gc_times.csv" % output_report_path, report_timestamp, gc_times)
                insert_comparison_data("%s/gc_times_comparison.csv" % output_report_path, gc_times, replace_release, release_name)

            if current_is_default and ("latency_indices_stats_p99" in metrics or "latency_nodes_stats_p99" in metrics):
                stats_latency = "%s,%s\n" % (v(metrics, "latency_indices_stats_p99"), v(metrics, "latency_nodes_stats_p99"))
                if not compare_mode:
                    write_report("%s/search_latency_stats.csv" % output_report_path, report_timestamp, stats_latency)
                insert_comparison_data("%s/search_latency_stats_comparison.csv" % output_report_path, stats_latency, replace_release, release_name)

            if current_is_default and "mem_segments" in metrics:
                # Date,Total heap used (MB),Doc values (MB),Terms (MB),Norms (MB),Stored fields (MB),Points (MB)
                total_memory = "%s,%s,%s,%s,%s,%s\n" % (v(metrics, "mem_segments"),
                                                        v(metrics, "mem_doc_values"),
                                                        v(metrics, "mem_terms"),
                                                        v(metrics, "mem_norms"),
                                                        v(metrics, "mem_fields"),
                                                        v(metrics, "mem_points"))
                if not compare_mode:
                    write_report("%s/segment_total_memory.csv" % output_report_path, report_timestamp, total_memory)
                insert_comparison_data("%s/segment_total_memory_comparison.csv" % output_report_path, total_memory, replace_release, release_name)

            if current_is_default and "indexing_time" in metrics:
                # Date,Indexing time (min),Merge time (min),Refresh time (min),Flush time (min),Merge throttle time (min)
                total_times = "%s,%s,%s,%s,%s\n" % (v(metrics, "indexing_time"),
                                                    v(metrics, "merge_time"),
                                                    v(metrics, "refresh_time"),
                                                    v(metrics, "flush_time"),
                                                    v(metrics, "merge_throttle_time"))
                if not compare_mode:
                    write_report("%s/indexing_total_times.csv" % output_report_path, report_timestamp, total_times)
                insert_comparison_data("%s/indexing_total_times_comparison.csv" % output_report_path, total_times, replace_release, release_name)

            if current_is_default and ("index_size" in metrics or "totally_written" in metrics):
                # Date,Final index size,Total bytes written
                disk_usage = "%s,%s\n" % (v(metrics, "index_size"), v(metrics, "totally_written"))
                if not compare_mode:
                    write_report("%s/disk_usage.csv" % output_report_path, report_timestamp, disk_usage)
                insert_comparison_data("%s/disk_usage_comparison.csv" % output_report_path, disk_usage, replace_release, release_name)

            if current_is_default and "query_latency_p99" in metrics:
                query_latency = "%s\n" % ",".join(metrics["query_latency_p99"])
                if not compare_mode:
                    write_report("%s/search_latency_queries.csv" % output_report_path, report_timestamp, query_latency)
                insert_comparison_data("%s/search_latency_queries_comparison.csv" % output_report_path, query_latency, replace_release, release_name)

            if "merge_time_parts" in metrics:
                merge_parts = "%s\n" % ",".join(metrics["merge_time_parts"])
                if not compare_mode:
                    write_report("%s/merge_parts.csv" % output_report_path, report_timestamp, merge_parts)
                insert_comparison_data("%s/merge_parts_comparison.csv" % output_report_path, merge_parts, replace_release, release_name)

            if not compare_mode:
                with open(meta_report_path) as csvfile:
                    meta_metrics = extract_meta_metrics(csvfile)

                if meta_metrics and "source_revision" in meta_metrics:
                    with open("%s/source_revision.csv" % output_report_path, "a") as f:
                        f.write("%s,%s\n" % (report_timestamp, meta_metrics["source_revision"]))

        if len(segment_count_metrics) > 0:
            segment_counts = "%s\n" % ",".join(segment_count_metrics)
            if not compare_mode:
                write_report("%s/segment_counts.csv" % output_report_path, report_timestamp, segment_counts)
            insert_comparison_data("%s/segment_counts_comparison.csv" % output_report_path, segment_counts, replace_release, release_name)

        if len(indexing_throughput_metrics) > 0:
            indexing_throughput = "%s\n" % ",".join(indexing_throughput_metrics)
            if not compare_mode:
                write_report("%s/indexing_throughput.csv" % output_report_path, report_timestamp, indexing_throughput)
            insert_comparison_data("%s/indexing_throughput_comparison.csv" % output_report_path, indexing_throughput, replace_release, release_name)


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
        "--target-host",
        help="The Elasticsearch node that should be targeted",
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
        choices=["nightly", "comparison"])
    parser.add_argument(
        "--release",
        help="Specify release string to use for comparison reports",
        default="master")
    parser.add_argument(
        "--replace-release",
        help="Specify the release string to replace for comparison reports")

    return parser.parse_args()


def main():
    args = parse_args()
    compare_mode = args.mode == "comparison"
    root_dir = config["root.dir"] if not args.override_root_dir else args.override_root_dir
    if compare_mode:
        if args.release.startswith("Docker"):
            command = DockerCommand(args.effective_start_date, args.target_host, root_dir, args.release)
        else:
            command = ReleaseCommand(args.effective_start_date, args.target_host, root_dir, args.release)
    else:
        configure_rally(args.dry_run)
        command = NightlyCommand(args.effective_start_date, args.target_host, root_dir, args.override_src_dir)

    rally_failure = run_rally(tracks, command, args.dry_run)
    replace_release = args.replace_release if args.replace_release else args.release
    report(args.effective_start_date, tracks, defaults, replace_release, args.release, root_dir, compare_mode)
    if rally_failure:
        exit(1)


if __name__ == "__main__":
    main()
