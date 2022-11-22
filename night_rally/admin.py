import argparse
import datetime
import json
import os
import sys
import uuid
from collections import namedtuple

import tabulate

from night_rally import client

def snake_case(s):
    return "_".join(s.lower().split())


def list_races(es, args):
    def format_dict(d):
        if d:
            return ", ".join(["%s=%s" % (k, v) for k, v in sorted(d.items())])
        else:
            return None

    limit = args.limit
    environment = args.environment
    track = args.track
    name = args.name
    license = args.license
    from_date = args.from_date
    to_date = args.to_date
    output_format = args.output_format

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
                                "gte": from_date,
                                "lte": to_date,
                                "format": "basic_date"
                            }
                        }
                    }
                ]
            }
        }
    }
    if track:
        query["query"]["bool"]["filter"].append({
            "term": {
                "track": track
            }
        })
    if name:
        query["query"]["bool"]["filter"].append({
            "term": {
                "user-tags.name": name
            }
        })

    if license:
        query["query"]["bool"]["filter"].append({
            "term": {
                "user-tags.license": license
            }
        })

    query["sort"] = [
        {
            "race-timestamp": "desc"
        },
        {
            "track": "asc"
        },
        {
            "challenge": "asc"
        },
        {
            "car": "asc"
        }
    ]

    result = es.search(index="rally-races-*", body=query, size=limit)
    headers = ["Race Timestamp",
               "Race Id",
               "Track",
               "Challenge",
               "Car",
               "ES Version",
               "Revision",
               "Rally Version",
               "Track Revision",
               "Team Revision",
               "User Tags"]
    Race = namedtuple("Race", " ".join([snake_case(h) for h in headers]))
    races = []

    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        if "user-tags" in src:
            user_tags = format_dict(src["user-tags"])
        elif "user-tag" in src:
            user_tags = src["user-tag"]
        else:
            user_tags = ""

        race_data = Race(src["race-timestamp"],
                         src["race-id"],
                         src["track"],
                         src.get("challenge"),
                         src["car"],
                         src["cluster"]["distribution-version"],
                         src["cluster"]["revision"],
                         src["rally-version"],
                         src["track-revision"],
                         src["cluster"]["team-revision"],
                         user_tags)

        races.append(race_data)

    if races:
        if output_format == "json":
            print(json.dumps([race._asdict() for race in races], indent=2))
        else:
            print(tabulate.tabulate(races, headers=headers))
    else:
        print("No results")


def list_annotations(es, args):
    limit = args.limit
    environment = args.environment
    track = args.track
    from_date = args.from_date
    to_date = args.to_date
    output_format = args.output_format
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
                                "gte": from_date,
                                "lte": to_date,
                                "format": "basic_date"
                            }
                        }
                    }
                ]
            }
        }
    }
    if track:
        query["query"]["bool"]["filter"].append({
            "term": {
                "track": track
            }
        })

    query["sort"] = [
        {
            "race-timestamp": "desc"
        },
        {
            "track": "asc"
        },
        {
            "chart": "asc"
        }
    ]

    result = es.search(index="rally-annotations", body=query, size=limit)
    headers = ["Annotation Id",
               "Timestamp",
               "Track",
               "Chart Type",
               "Chart Name",
               "Message"]
    Annotation = namedtuple("Annotation", " ".join([snake_case(h) for h in headers]))
    annotations = []

    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        annotation_data = Annotation(hit["_id"],
                                     src["race-timestamp"],
                                     src.get("track", ""),
                                     src.get("chart", ""),
                                     src.get("chart-name", ""),
                                     src["message"])
        annotations.append(annotation_data)

    if annotations:
        if output_format == "json":
            print(json.dumps([a._asdict() for a in annotations], indent=2))
        else:
            print(tabulate.tabulate(annotations, headers=headers))
    else:
        print("No results")


def _at_midnight(race_timestamp):
    TIMESTAMP_FMT = "%Y%m%dT%H%S%MZ"
    date = datetime.datetime.strptime(race_timestamp, TIMESTAMP_FMT)
    date = date.replace(hour=0, minute=0, second=0, tzinfo=datetime.timezone.utc)
    return date.strftime(TIMESTAMP_FMT)


def add_annotation(es, args):
    environment = args.environment
    # To line up annotations with chart data points, use midnight of day N as this is
    # what the chart use too.
    race_timestamp = _at_midnight(args.race_timestamp)
    track = args.track
    chart_type = args.chart_type
    chart_name = args.chart_name
    message = args.message
    annotation_id = str(uuid.uuid4())
    dry_run = args.dry_run

    if dry_run:
        print(f"Would add annotation with message [{message}] for environment=[{environment}], race timestamp=[{race_timestamp}], "
              f"track=[{track}], chart type=[{chart_type}], chart name=[{chart_name}]")
    else:
        if not es.indices.exists(index="rally-annotations"):
            cwd = os.path.dirname(os.path.realpath(__file__))
            body = open(os.path.join(cwd, "resources", "annotation-mapping.json"), "rt").read()
            es.indices.create(index="rally-annotations", body=body)
        resp = es.index(index="rally-annotations", id=annotation_id, body={
            "environment": environment,
            "race-timestamp": race_timestamp,
            "track": track,
            "chart": chart_type,
            "chart-name": chart_name,
            "message": message
        })
        print(f"Successfully added annotation [{resp['_id']}].")


def delete_annotation(es, args):
    import elasticsearch
    annotations = args.id.split(",")
    if args.dry_run:
        if len(annotations) == 1:
            print("Would delete annotation with id [%s]." % annotations[0])
        else:
            print("Would delete %s annotations: %s." % (len(annotations), annotations))
    else:
        for annotation_id in annotations:
            try:
                es.delete(index="rally-annotations", id=annotation_id)
                print("Successfully deleted [%s]." % annotation_id)
            except elasticsearch.TransportError as e:
                if e.status_code == 404:
                    print("Did not find [%s]." % annotation_id)
                else:
                    raise


def delete_race(es, args):
    import elasticsearch

    def do_delete(index, body, race_id):
        try:
            return es.delete_by_query(index=index, body=body)
        except elasticsearch.TransportError as e:
            if e.status_code == 404:
                print("Did not find [%s]." % race_id)
            else:
                raise

    environment = args.environment
    races = args.id.split(",")
    if args.dry_run:
        if len(races) == 1:
            print("Would delete race with id [%s] in environment [%s]." % (races[0], environment))
        else:
            print("Would delete %s races: %s in environment [%s]." % (len(races), races, environment))
    else:
        for race_id in races:
            selector = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "environment": environment
                                }
                            },
                            {
                                "term": {
                                    "race-id": race_id
                                }
                            }
                        ]
                    }
                }
            }
            do_delete(index="rally-races-*", body=selector, race_id=race_id)
            do_delete(index="rally-results-*", body=selector, race_id=race_id)
            do_delete(index="rally-metrics-*", body=selector, race_id=race_id)

            print("Successfully deleted [%s] in environment [%s]." % (race_id, environment))


def arg_parser():
    def positive_number(v):
        value = int(v)
        if value <= 0:
            raise argparse.ArgumentTypeError("must be positive but was %s" % value)
        return value

    def valid_date(v):
        pattern = "%Y%m%d"
        try:
            datetime.datetime.strptime(v, pattern)
            # don't convert, just check that the format is correct, we'll use the string value later on anyway
            return v
        except ValueError:
            msg = "[{}] does not conform to the pattern [yyyyMMdd]".format(v)
            raise argparse.ArgumentTypeError(msg)

    parser = argparse.ArgumentParser(description="Admin tool for Elasticsearch benchmarks",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers(
        title="subcommands",
        dest="subcommand",
        help="")
    # the keyword argument in #add_subparsers() only works in Python 3.7+.
    # See https://docs.python.org/3.7/library/argparse.html#argparse.ArgumentParser.add_subparsers
    subparsers.required = True

    # list races --max-results=20
    # list annotations --max-results=20
    list_parser = subparsers.add_parser("list", help="List configuration options")
    list_parser.add_argument(
        "configuration",
        metavar="configuration",
        help="What the admin tool should list. Possible values are: races, annotations",
        choices=["races", "annotations"])

    list_parser.add_argument(
        "--limit",
        help="Limit the number of search results (default: 20).",
        type=positive_number,
        default=20,
    )
    list_parser.add_argument(
        "--environment",
        help="Show only records from this environment",
        required=True
    )
    list_parser.add_argument(
        "--track",
        help="Show only records from this track",
        default=None
    )
    list_parser.add_argument(
        "--license",
        help="Show only records from with corresponding 'license' user tag",
        default=None
    )
    list_parser.add_argument(
        "--name",
        help="Show only records from with corresponding 'name' user tag",
        default=None
    )
    list_parser.add_argument(
        "--from-date",
        help="Show only records on or after this date (format: yyyyMMdd)",
        type=valid_date,
        default=None
    )
    list_parser.add_argument(
        "--to-date",
        help="Show only records before or on this date (format: yyyyMMdd)",
        type=valid_date,
        default=None
    )
    list_parser.add_argument(
        "--format",
        help="Print results as text or json",
        choices=["text", "json"],
        default="text",
        dest="output_format"
    )

    # if no "track" is given -> annotate all tracks
    # "chart-type" indicates the graph. If no chart-type, is given, it is empty -> we need to write the queries to that we update all chart
    #
    # add [annotation] --environment=nightly --race-timestamp --track --chart-type --chart-name --text
    add_parser = subparsers.add_parser("add", help="Add records")
    add_parser.add_argument(
        "configuration",
        metavar="configuration",
        help="",
        choices=["annotation"])
    add_parser.add_argument(
        "--dry-run",
        help="Just show what would be done but do not apply the operation.",
        default=False,
        action="store_true"
    )
    add_parser.add_argument(
        "--environment",
        help="Environment (default: nightly)",
        default="nightly"
    )
    add_parser.add_argument(
        "--race-timestamp",
        help="Race timestamp"
    )
    add_parser.add_argument(
        "--track",
        help="Track. If none given, applies to all tracks",
        default=None
    )
    add_parser.add_argument(
        "--chart-type",
        help="Chart type to target. If none given, applies to all charts.",
        choices=["query", "script", "stats", "indexing", "gc", "index_times", "merge_times", "merge_count",
                 "refresh_times", "segment_count", "io", "ml_processing_time"],
        default=None
    )
    add_parser.add_argument(
        "--chart-name",
        help="A chart name to target. If none given, applies to all charts.",
        default=None
    )
    add_parser.add_argument(
        "--message",
        help="Annotation message",
        required=True
    )

    delete_parser = subparsers.add_parser("delete", help="Delete records")
    delete_parser.add_argument(
        "configuration",
        metavar="configuration",
        help="",
        choices=["annotation", "race"])
    delete_parser.add_argument(
        "--dry-run",
        help="Just show what would be done but do not apply the operation.",
        default=False,
        action="store_true"
    )
    delete_parser.add_argument(
        "--id",
        help="Ids of the items to delete. Separate multiple ids with a comma.",
        required=True
    )
    delete_parser.add_argument(
        "--environment",
        help="Environment (default: nightly)",
        default="nightly"
    )
    return parser


def main():
    parser = arg_parser()
    args = parser.parse_args()

    es = client.create_client(args.environment)
    if args.subcommand == "list":
        if args.configuration == "races":
            list_races(es, args)
        elif args.configuration == "annotations":
            list_annotations(es, args)
        else:
            print("Do not know how to list [%s]" % args.configuration, file=sys.stderr)
            exit(1)
    elif args.subcommand == "add" and args.configuration == "annotation":
        add_annotation(es, args)
    elif args.subcommand == "delete" and args.configuration == "annotation":
        delete_annotation(es, args)
    elif args.subcommand == "delete" and args.configuration == "race":
        delete_race(es, args)
    else:
        parser.print_help(file=sys.stderr)
        exit(1)


if __name__ == '__main__':
    main()
