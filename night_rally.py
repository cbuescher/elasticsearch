import argparse
import collections
import datetime
import time
import csv
import re
import os
import errno
import shutil
import logging
import fileinput

tracks = collections.OrderedDict()

tracks["geonames"] = [
    ["append-no-conflicts", "defaults"],
    ["append-no-conflicts", "4gheap"],
    ["append-fast-no-conflicts", "4gheap"],
    ["append-fast-with-conflicts", "4gheap"],
    ["append-no-conflicts", "two_nodes"],
    ["append-no-conflicts", "verbose_iw"]
]

tracks["percolator"] = [
    ["append-no-conflicts", "4gheap"]
]

tracks["geopoint"] = [
    ["append-no-conflicts", "defaults"],
    ["append-no-conflicts", "4gheap"],
    ["append-fast-no-conflicts", "4gheap"],
    ["append-fast-with-conflicts", "4gheap"],
    ["append-no-conflicts", "two_nodes"]
]

tracks["pmc"] = [
    #["append-no-conflicts", "defaults"],
    ["append-no-conflicts", "4gheap"],
    ["append-fast-no-conflicts", "4gheap"],
    ["append-fast-with-conflicts", "4gheap"],
    #["append-no-conflicts", "two_nodes"]
]

# default challenge / car per track
defaults = {
    "geonames": ("append-no-conflicts", "defaults"),
    "percolator": ("append-no-conflicts", "4gheap"),
    "geopoint": ("append-no-conflicts", "defaults"),
    "pmc": ("append-no-conflicts", "4gheap")
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


def run(tracks, effective_start_date, override_src_dir):
    _configure_rally()
    _run_rally(effective_start_date, tracks)


def _configure_rally():
    user_home = os.getenv("HOME")
    root = os.path.dirname(os.path.realpath(__file__))
    source = "%s/resources/rally-nightly.ini" % root
    destination = "%s/.rally/rally-nightly.ini" % user_home
    logger.info("Copying rally configuration from [%s] to [%s]" % (source, destination))
    ensure_dir("%s/.rally" % user_home)
    shutil.copyfile(source, destination)
    # materialize current user home
    with fileinput.input(files=destination, inplace=True) as f:
        for line in f:
            print(line.replace("~", user_home))


def _run_rally(effective_start_date, tracks, override_src_dir, system=os.system):
    ts = date_for_cmd_param(effective_start_date)
    revision_ts = to_iso8601(effective_start_date)

    if override_src_dir is not None:
        override = " --override-src-dir=%s" % override_src_dir
    else:
        override = ""

    root_dir = config["root.dir"]
    report_root_dir = config["report.base.dir"]

    pipeline = "from-sources-complete"
    for track, setups in tracks.items():
        for setup in setups:
            challenge, car = setup
            logger.info("Running Rally on track [%s] with challenge [%s] and car [%s]" % (track, challenge, car))
            report_path = "%s/%s/rally/%s/%s/%s/%s/report.csv" % (root_dir, report_root_dir,
                                                                  date_for_path(effective_start_date), track,
                                                                  challenge, car)
            if system(
                "rally --configuration-name=nightly --pipeline={6} --quiet --revision \"@{0}\" --effective-start-date \"{1}\" "
                "--track={2} --challenge={3} --car={4} --report-format=csv --report-file={5}{7}"
                    .format(revision_ts, ts, track, challenge, car, report_path, pipeline, override)):
                logger.error("Failed to run track [%s]. Please check the logs." % track)
            # after we've executed the first benchmark, there is no reason to build again from sources
            pipeline = "from-sources-skip-build"


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
    "99.0th percentile latency": "query_latency_p99",
    "Merge time \(.*": "merge_time_parts"
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
    if re.match(metric_pattern, metric_name):
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


def extract_metrics(source_report):
    metrics = {}
    for row in csv.reader(source_report):
        for metric_pattern, metric_key in METRICS_TO_KEY.items():
            metric_name = row[0]
            op_name = row[1]
            metric_value = row[2]

            final_key = key_for(metric_pattern, metric_key, metric_name, op_name)
            if final_key:
                if is_multi_valued(final_key):
                    if final_key not in metrics:
                        metrics[final_key] = []
                    metrics[final_key].append(metric_value)
                else:
                    metrics[final_key] = metric_value
    return metrics


def report(effective_start_date, tracks, default_setup_per_track):
    """
    Publishes all data from the provided trial run.

    :param effective_start_date: A timestamp for which we should publish data.
    :param tracks: A hash of all tracks that have been run and their challenges.
    :param default_setup_per_track: A hash of the default challenge / car per track.

    """
    timestamp = date_for_path(effective_start_date)
    # this timestamp gets used in the report files
    report_timestamp = date_for_cmd_param(effective_start_date)

    for track, setups in tracks.items():
        root_dir = config["root.dir"]
        report_root_dir = config["report.base.dir"]
        output_report_path = "%s/%s/out/%s" % (root_dir, report_root_dir, track)

        segment_count_metrics = []
        indexing_throughput_metrics = []

        for setup in setups:
            challenge, car = setup
            current_is_default = is_default_setup(default_setup_per_track[track], setup)
            report_path = "%s/%s/rally/%s/%s/%s/%s/report.csv" % (root_dir, report_root_dir, timestamp, track, challenge, car)

            if not os.path.isfile(report_path):
                logger.warn("[%s] does not exist. Skipping track [%s], challenge [%s], car [%s]."
                            % (report_path, track, challenge, car))
                continue

            with open(report_path) as csvfile:
                metrics = extract_metrics(csvfile)

            if "segment_count" in metrics:
                segment_count_metrics.append(metrics["segment_count"])

            # Beware: this one is one column per series!
            if "median_indexing_throughput" in metrics:
                indexing_throughput_metrics.append(metrics["median_indexing_throughput"])

            if current_is_default and "cpu_usage" in metrics:
                with open("%s/indexing_cpu_usage.csv" % output_report_path, "a") as f:
                    f.write("%s,%s\n" % (report_timestamp, metrics["cpu_usage"]))

            if current_is_default and ("young_gen_gc" in metrics or "old_gen_gc" in metrics):
                with open("%s/gc_times.csv" % output_report_path, "a") as f:
                    f.write("%s,%s,%s\n" % (report_timestamp, v(metrics, "young_gen_gc"), v(metrics, "old_gen_gc")))

            if current_is_default and ("latency_indices_stats_p99" in metrics or "latency_nodes_stats_p99" in metrics):
                with open("%s/search_latency_stats.csv" % output_report_path, "a") as f:
                    f.write("%s,%s,%s\n" % (
                        report_timestamp, v(metrics, "latency_indices_stats_p99"), v(metrics, "latency_nodes_stats_p99")))

            if current_is_default and "mem_segments" in metrics:
                # Date,Total heap used (MB),Doc values (MB),Terms (MB),Norms (MB),Stored fields (MB),Points (MB)
                with open("%s/segment_total_memory.csv" % output_report_path, "a") as f:
                    f.write("%s,%s,%s,%s,%s,%s,%s\n" % (report_timestamp,
                                                        v(metrics, "mem_segments"),
                                                        v(metrics, "mem_doc_values"),
                                                        v(metrics, "mem_terms"),
                                                        v(metrics, "mem_norms"),
                                                        v(metrics, "mem_fields"),
                                                        v(metrics, "mem_points")))

            if current_is_default and "indexing_time" in metrics:
                # Date,Indexing time (min),Merge time (min),Refresh time (min),Flush time (min),Merge throttle time (min)
                with open("%s/indexing_total_times.csv" % output_report_path, "a") as f:
                    f.write("%s,%s,%s,%s,%s,%s\n" % (report_timestamp,
                                                     v(metrics, "indexing_time"),
                                                     v(metrics, "merge_time"),
                                                     v(metrics, "refresh_time"),
                                                     v(metrics, "flush_time"),
                                                     v(metrics, "merge_throttle_time")))

            if current_is_default and ("index_size" in metrics or "totally_written" in metrics):
                # Date,Final index size,Total bytes written
                with open("%s/disk_usage.csv" % output_report_path, "a") as f:
                    f.write("%s,%s,%s\n" % (report_timestamp, v(metrics, "index_size"), v(metrics, "totally_written")))

            if current_is_default and "query_latency_p99" in metrics:
                with open("%s/search_latency_queries.csv" % output_report_path, "a") as f:
                    f.write("%s,%s\n" % (report_timestamp, ",".join(metrics["query_latency_p99"])))

            if "merge_time_parts" in metrics:
                with open("%s/merge_parts.csv" % output_report_path, "a") as f:
                    f.write("%s,%s\n" % (report_timestamp, ",".join(metrics["merge_time_parts"])))

        if len(segment_count_metrics) > 0:
            with open("%s/segment_counts.csv" % output_report_path, "a") as f:
                f.write("%s,%s\n" % (report_timestamp, ",".join(segment_count_metrics)))

        if len(indexing_throughput_metrics) > 0:
            with open("%s/indexing_throughput.csv" % output_report_path, "a") as f:
                f.write("%s,%s\n" % (report_timestamp, ",".join(indexing_throughput_metrics)))


def parse_args():
    parser = argparse.ArgumentParser(prog="night_rally", description="Nightly Elasticsearch benchmarks")

    parser.add_argument(
        "--effective-start-date",
        help="Passes this date as start date to Rally (format: %Y-%m-%d %H:%M:%S). Needed for consistent results for multiple trial runs",
        required=True,
        type=lambda s: datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S"))
    parser.add_argument(
        "--override-src-dir",
        help=argparse.SUPPRESS,
        default=None)

    return parser.parse_args()


def main():
    args = parse_args()

    run(tracks, args.effective_start_date, args.override_src_dir)
    report(args.effective_start_date, tracks, defaults)


if __name__ == "__main__":
    main()
