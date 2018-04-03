import os
import sys
import argparse
import client
# non-standard! requires setup.py!!
import tabulate


def list_races(es, args):
    def format_dict(d):
        if d:
            return ", ".join(["%s=%s" % (k, v) for k, v in sorted(d.items())])
        else:
            return None


    limit = args.limit
    environment = args.environment
    track = args.track
    car = args.car
    challenge = args.challenge

    msg = "Listing %d most recent races for" % limit
    if track:
        msg += " track %s" % track
    if challenge:
        msg += " challenge %s" % challenge
    if car:
        msg += " car %s" % car
    msg += " in environment %s.\n" % environment
    print(msg)

    query = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "term": {
                            "environment": environment
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
    if challenge:
        query["query"]["bool"]["filter"].append({
            "term": {
                "challenge": challenge
            }
        })

    if car:
        query["query"]["bool"]["filter"].append({
            "term": {
                "car": car
            }
        })

    query["sort"] = [
        {
            "trial-timestamp": "desc"
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
    races = []
    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        if "user-tags" in src:
            user_tags = format_dict(src["user-tags"])
        elif "user-tag" in src:
            user_tags = src["user-tag"]
        else:
            user_tags = ""

        races.append([src["trial-timestamp"], src["track"], src["challenge"], src["car"],
                      src["cluster"]["distribution-version"], src["cluster"]["revision"], user_tags])
    if races:
        print(tabulate.tabulate(races, headers=["Race Timestamp", "Track", "Challenge", "Car", "Version", "Revision", "User Tags"]))
    else:
        print("No results")


def list_annotations(es, args):
    limit = args.limit
    environment = args.environment
    track = args.track
    if track:
        print("Listing %d most recent annotations in environment %s for track %s.\n" % (limit, environment, track))
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
                            "term": {
                                "track": track
                            }
                        }
                    ]
                }

            }
        }
    else:
        print("Listing %d most recent annotations in environment %s.\n" % (limit, environment))
        query = {
            "query": {
                "term": {
                    "environment": environment
                }
            },
        }
    query["sort"] = [
        {
            "trial-timestamp": "desc"
        },
        {
            "track": "asc"
        },
        {
            "chart": "asc"
        }
    ]

    result = es.search(index="rally-annotations", body=query, size=limit)
    annotations = []
    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        annotations.append([hit["_id"], src["trial-timestamp"], src.get("track", ""), src.get("chart", ""), src["message"]])
    if annotations:
        print(tabulate.tabulate(annotations, headers=["Annotation Id", "Timestamp", "Track", "Chart", "Message"]))
    else:
        print("No results")


def add_annotation(es, args):
    environment = args.environment
    trial_timestamp = args.trial_timestamp
    track = args.track
    chart = args.chart
    message = args.message
    dry_run = args.dry_run

    if dry_run:
        print("Would add annotation with message [%s] for environment=[%s], trial timestamp=[%s], track=[%s], chart=[%s]" %
              (message, environment, trial_timestamp, track, chart))
    else:
        if not es.indices.exists(index="rally-annotations"):
            body = open("%s/resources/annotation-mapping.json" % os.path.dirname(os.path.realpath(__file__)), "rt").read()
            es.indices.create(index="rally-annotations", body=body)
        es.index(index="rally-annotations", doc_type="type", body={
            "environment": environment,
            "trial-timestamp": trial_timestamp,
            "track": track,
            "chart": chart,
            "message": message
        })


def delete_annotation(es, args):
    import elasticsearch
    annotations = args.id.split(",")
    if args.dry_run:
        if len(annotations) == 1:
            print("Would delete annotation with id [%s]." % annotations[0])
        else:
            print("Would delete %s annotations: %s." % (len(annotations, annotations)))
    else:
        for annotation_id in annotations:
            try:
                es.delete(index="rally-annotations", doc_type="type", id=annotation_id)
                print("Successfully deleted [%s]." % annotation_id)
            except elasticsearch.TransportError as e:
                if e.status_code == 404:
                    print("Did not find [%s]." % annotation_id)
                else:
                    raise


def arg_parser():
    def positive_number(v):
        value = int(v)
        if value <= 0:
            raise argparse.ArgumentTypeError("must be positive but was %s" % value)
        return value

    parser = argparse.ArgumentParser(description="Admin tool for Elasticsearch benchmarks",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers(
        title="subcommands",
        dest="subcommand",
        help="")

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
        "--car",
        help="Show only records for this car",
        default=None
    )
    list_parser.add_argument(
        "--challenge",
        help="Show only records for this challenge",
        default=None
    )

    # if no "track" is given -> annotate all tracks
    # "chart" indicates the graph. If no chart, is given, it is empty -> we need to write the queries to that we update all chart
    #
    # add [annotation] --environment=nightly --trial-timestamp --track --chart --text
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
        "--trial-timestamp",
        help="Trial timestamp"
    )
    add_parser.add_argument(
        "--track",
        help="Track. If none given, applies to all tracks",
        default=None
    )
    add_parser.add_argument(
        "--chart",
        help="Chart to target. If none given, applies to all charts.",
        choices=['query', 'script', 'stats', 'indexing', 'gc', 'index_times', 'merge_times', 'segment_count', 'segment_memory', 'io'],
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
        choices=["annotation"])
    delete_parser.add_argument(
        "--dry-run",
        help="Just show what would be done but do not apply the operation.",
        default=False,
        action="store_true"
    )
    delete_parser.add_argument(
        "--id",
        help="Id of the annotation to delete. Separate multiple ids with a comma.",
        required=True
    )
    return parser


def main():
    parser = arg_parser()
    es = client.create_client()

    args = parser.parse_args()
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
    else:
        parser.print_help(file=sys.stderr)
        exit(1)


if __name__ == '__main__':
    main()
