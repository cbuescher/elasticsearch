import uuid
import json
import os

all_tracks_and_challenges = {
    "nested": [
        ["nested-search-challenge", "4gheap"],
    ],
    "geonames": [
        ["append-no-conflicts", "defaults"],
        ["append-no-conflicts-index-only", "4gheap"],
        ["append-sorted-no-conflicts", "4gheap"],
        ["append-fast-with-conflicts", "4gheap"],
        ["append-no-conflicts-index-only-1-replica", "two_nodes"],
    ],
    "percolator": [
        ["append-no-conflicts", "4gheap"],
    ],
    "geopoint": [
        ["append-no-conflicts", "defaults"],
        ["append-no-conflicts-index-only", "4gheap"],
        ["append-fast-with-conflicts", "4gheap"],
        ["append-no-conflicts-index-only-1-replica", "two_nodes"],
    ],
    "pmc": [
        ["append-no-conflicts-index-only", "defaults"],
        ["append-no-conflicts", "4gheap"],
        ["append-sorted-no-conflicts", "4gheap"],
        ["append-fast-with-conflicts", "4gheap"],
        ["append-no-conflicts-index-only-1-replica", "two_nodes"],
    ],
    "nyc_taxis": [
        ["append-no-conflicts", "4gheap"],
        ["append-sorted-no-conflicts-index-only", "4gheap"],
    ],
    "logging": [
        ["append-no-conflicts-index-only", "defaults"],
        ["append-no-conflicts", "4gheap"],
        ["append-sorted-no-conflicts", "4gheap"],
    ],
    "noaa": [
        ["append-no-conflicts", "defaults"]
    ]
}

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


def challenges(track_name):
    user_home = os.getenv("HOME")
    contents = open("%s/.rally/benchmarks/tracks/default/%s/challenges/default.json" % (user_home, track_name)).read()
    contents = "[%s]" % contents
    return json.loads(contents)


def find_challenge(all_challenges, name):
    for c in all_challenges:
        if c["name"] == name:
            return c
    return None


def generate_index_ops():
    def tracks_for_index():
        all_tracks = []
        for track, challenges_cars in all_tracks_and_challenges.items():
            challenges_of_track = challenges(track)
            cci = []
            for cc in challenges_cars:
                challenge = cc[0]
                car = cc[1]
                index_op = find_challenge(challenges_of_track, challenge)["schedule"][0]["operation"]
                cci.append((challenge, car, index_op))
            all_tracks.append((track, cci))
        return all_tracks

    structures = []
    for track, cci in tracks_for_index():
        title = "release-%s-indexing-throughput" % track

        filters = ""
        for idx, item in enumerate(cci):
            challenge, car, index_op = item
            if idx > 0:
                filters = filters + ","
            label = "%s-%s" % (challenge, car)
            filters = filters + "{\"input\":{\"query\":{\"query_string\":{\"analyze_wildcard\":true,\"query\":\"operation:%s AND challenge:%s AND car:%s\"}}},\"label\":\"%s\"}" % (index_op, challenge, car, label)

        s = {
            "_id": str(uuid.uuid4()),
            "_type": "visualization",
            "_source": {
                "title": title,
                "visState": "{\"aggs\":[{\"enabled\":true,\"id\":\"1\",\"params\":{\"customLabel\":\"Median Indexing Throughput [docs/s]\",\"field\":\"value.median\",\"percents\":[50]},\"schema\":\"metric\",\"type\":\"median\"},"
                            "{\"enabled\":true,\"id\":\"2\",\"params\":{\"field\":\"distribution-version\",\"order\":\"asc\",\"orderBy\":\"_term\",\"size\":10},\"schema\":\"segment\",\"type\":\"terms\"},{\"enabled\":true,\"id\":\"3\",\"params\":"
                            "{\"field\":\"user-tag\",\"order\":\"desc\",\"orderBy\":\"_term\",\"size\":10},\"schema\":\"group\",\"type\":\"terms\"},{\"enabled\":true,\"id\":\"4\",\"params\":"
                            "{\"filters\":[%s]"
                            ",\"row\":true},\"schema\":\"split\",\"type\":\"filters\"}],\"listeners\":{},\"params\":{\"addLegend\":true,"
                            "\"addTimeMarker\":false,\"addTooltip\":true,\"categoryAxes\":[{\"id\":\"CategoryAxis-1\",\"labels\":{\"show\":true,"
                            "\"truncate\":100},\"position\":\"bottom\",\"scale\":{\"type\":\"linear\"},\"show\":true,\"style\":{},"
                            "\"title\":{\"text\":\"distribution-version: Ascending\"},\"type\":\"category\"}],\"defaultYExtents\":false,"
                            "\"drawLinesBetweenPoints\":true,\"grid\":{\"categoryLines\":false,\"style\":{\"color\":\"#eee\"}},"
                            "\"interpolate\":\"linear\",\"legendPosition\":\"right\",\"radiusRatio\":9,\"scale\":\"linear\","
                            "\"seriesParams\":[{\"data\":{\"id\":\"1\",\"label\":\"Median Indexing Throughput [docs/s]\"},"
                            "\"drawLinesBetweenPoints\":true,\"mode\":\"stacked\",\"show\":\"true\",\"showCircles\":true,\"type\":"
                            "\"histogram\",\"valueAxis\":\"ValueAxis-1\"}],\"setYExtents\":false,\"showCircles\":true,\"times\":[],"
                            "\"valueAxes\":[{\"id\":\"ValueAxis-1\",\"labels\":{\"filter\":false,\"rotate\":0,\"show\":true,\"truncate\":100},"
                            "\"name\":\"LeftAxis-1\",\"position\":\"left\",\"scale\":{\"mode\":\"normal\",\"type\":\"linear\"},\"show\":true,"
                            "\"style\":{},\"title\":{\"text\":\"Median Indexing Throughput [docs/s]\"},\"type\":\"value\"}]},\"title\":\"%s\",\"type\":\"histogram\"}" % (filters, title),
                "uiStateJSON": "{\"vis\":{\"legendOpen\":true}}",
                "description": "",
                "version": 1,
                "kibanaSavedObjectMeta": {
                    "searchSourceJSON": "{\"index\":\"rally-results-*\",\"query\":{\"query_string\":{\"analyze_wildcard\":true,\"query\":\"environment:release AND active:true AND track:%s AND name:throughput\"}},\"filter\":[]}" % track
                }
            }
        }
        structures.append(s)

    return structures


def default_tracks():
    all_tracks = []
    for track, challenge_car in defaults.items():
        challenge, car = challenge_car
        default_challenge = challenges(track)[0]
        # default challenge is usually the first one. No need for complex logic
        assert default_challenge["default"]
        # filter queries
        queries = [t["operation"] for t in default_challenge["schedule"] if
                   not (t["operation"].startswith("index") or t["operation"] in ["force-merge", "node-stats"])]
        all_tracks.append((track, challenge, car, queries))

    return all_tracks


def generate_queries():
    # output JSON structures
    structures = []
    for track, challenge, car, queries in default_tracks():
        for q in queries:
            title = "release-%s-%s-p99-latency" % (track, q)
            label = "Query Latency [ms]"
            metric = "service_time"

            s = {
                "_id": str(uuid.uuid4()),
                "_type": "visualization",
                "_source": {
                    "title": title,
                    "visState": "{\"title\":\"%s\",\"type\":\"histogram\",\"params\":{\"addLegend\":true,\"addTimeMarker\":false,\"addTooltip\":true,\""
                                "categoryAxes\":[{\"id\":\"CategoryAxis-1\",\"labels\":{\"show\":true,\"truncate\":100},\"position\":\"bottom\",\""
                                "scale\":{\"type\":\"linear\"},\"show\":true,\"style\":{},\"title\":{\"text\":\"distribution-version: Ascending\"},\"type\":\"category\"}],"
                                "\"defaultYExtents\":false,\"drawLinesBetweenPoints\":true,\"grid\":{\"categoryLines\":false,\"style\":{\"color\":\"#eee\"}},"
                                "\"interpolate\":\"linear\",\"legendPosition\":\"right\",\"radiusRatio\":9,\"scale\":\"linear\",\""
                                "seriesParams\":[{\"data\":{\"id\":\"1\",\"label\":\"%s\"},\"drawLinesBetweenPoints\":true,"
                                "\"mode\":\"stacked\",\"show\":\"true\",\"showCircles\":true,\"type\":\"histogram\",\"valueAxis\":\"ValueAxis-1\"}],"
                                "\"setYExtents\":false,\"showCircles\":true,\"times\":[],\"valueAxes\":[{\"id\":\"ValueAxis-1\","
                                "\"labels\":{\"filter\":false,\"rotate\":0,\"show\":true,\"truncate\":100},\"name\":\"LeftAxis-1\","
                                "\"position\":\"left\",\"scale\":{\"mode\":\"normal\",\"type\":\"linear\"},\"show\":true,\"style\":{},"
                                "\"title\":{\"text\":\"%s\"},\"type\":\"value\"}]},\"aggs\":[{\"id\":\"1\","
                                "\"enabled\":true,\"type\":\"median\",\"schema\":\"metric\",\"params\":{\"field\":\"value.99_0\","
                                "\"percents\":[50],\"customLabel\":\"%s\"}},{\"id\":\"2\",\"enabled\":true,\"type\":\"terms\",\"schema\":"
                                "\"segment\",\"params\":{\"field\":\"distribution-version\",\"size\":10,\"order\":\"asc\","
                                "\"orderBy\":\"_term\"}},{\"id\":\"3\",\"enabled\":true,\"type\":\"terms\",\"schema\":\"group\","
                                "\"params\":{\"field\":\"user-tag\",\"size\":10,\"order\":\"desc\",\"orderBy\":\"_term\"}}],"
                                "\"listeners\":{}}" % (title, label, label, label),
                    "uiStateJSON": "{}",
                    "description": "",
                    "version": 1,
                    "kibanaSavedObjectMeta": {
                        "searchSourceJSON": "{\"index\":\"rally-results-*\",\"query\":{\"query_string\":"
                                            "{\"query\":\"environment:release AND active:true AND track:%s AND name:%s AND operation:%s AND challenge:%s AND car:%s\",\"analyze_wildcard\":true}},\"filter\":[]}" % (
                                                track, metric, q, challenge, car)
                    }
                }
            }
            structures.append(s)
    return structures


def generate_io():
    # output JSON structures
    structures = []
    for track, challenge, car, queries in default_tracks():
        title = "release-%s-io" % track

        s = {
            "_id": str(uuid.uuid4()),
            "_type": "visualization",
            "_source": {
                "title": title,
                "visState": "{\"title\":\"%s\",\"type\":\"histogram\",\"params\":{\"addLegend\":true,\"addTimeMarker\":false,\"addTooltip\":true,\"categoryAxes\":[{\"id\":\"CategoryAxis-1\",\"labels\":{\"show\":true,\"truncate\":100},\"position\":\"bottom\",\"scale\":{\"type\":\"linear\"},\"show\":true,\"style\":{},\"title\":{\"text\":\"filters\"},\"type\":\"category\"}],\"defaultYExtents\":false,\"drawLinesBetweenPoints\":true,\"grid\":{\"categoryLines\":false,\"style\":{\"color\":\"#eee\"}},\"interpolate\":\"linear\",\"legendPosition\":\"right\",\"radiusRatio\":9,\"scale\":\"linear\",\"seriesParams\":[{\"data\":{\"id\":\"1\",\"label\":\"[Bytes]\"},\"drawLinesBetweenPoints\":true,\"mode\":\"stacked\",\"show\":\"true\",\"showCircles\":true,\"type\":\"histogram\",\"valueAxis\":\"ValueAxis-1\"}],\"setYExtents\":false,\"showCircles\":true,\"times\":[],\"valueAxes\":[{\"id\":\"ValueAxis-1\",\"labels\":{\"filter\":false,\"rotate\":0,\"show\":true,\"truncate\":100},\"name\":\"LeftAxis-1\",\"position\":\"left\",\"scale\":{\"mode\":\"normal\",\"type\":\"linear\"},\"show\":true,\"style\":{},\"title\":{\"text\":\"[Bytes]\"},\"type\":\"value\"}]},\"aggs\":[{\"id\":\"1\",\"enabled\":true,\"type\":\"median\",\"schema\":\"metric\",\"params\":{\"field\":\"value.single\",\"percents\":[50],\"customLabel\":\"[Bytes]\"}},{\"id\":\"2\",\"enabled\":true,\"type\":\"filters\",\"schema\":\"segment\",\"params\":{\"filters\":[{\"input\":{\"query\":{\"query_string\":{\"analyze_wildcard\":true,\"query\":\"name:index_size\"}}},\"label\":\"Index size\"},{\"input\":{\"query\":{\"query_string\":{\"analyze_wildcard\":true,\"query\":\"name:bytes_written\"}}},\"label\":\"Bytes written\"}]}},{\"id\":\"3\",\"enabled\":true,\"type\":\"terms\",\"schema\":\"split\",\"params\":{\"field\":\"distribution-version\",\"size\":10,\"order\":\"asc\",\"orderBy\":\"_term\",\"row\":false}},{\"id\":\"4\",\"enabled\":true,\"type\":\"terms\",\"schema\":\"group\",\"params\":{\"field\":\"user-tag\",\"size\":5,\"order\":\"desc\",\"orderBy\":\"_term\"}}],\"listeners\":{}}" % title,
                "uiStateJSON": "{}",
                "description": "",
                "version": 1,
                "kibanaSavedObjectMeta": {
                    "searchSourceJSON": "{\"index\":\"rally-results-*\",\"query\":{\"query_string\":{\"query\":\"environment:release AND active:true AND track:%s AND challenge:%s AND car:%s\",\"analyze_wildcard\":true}},\"filter\":[]}" % (track, challenge, car)
                }
            }
        }
        structures.append(s)

    return structures


def generate_gc():
    structures = []
    for track, challenge, car, queries in default_tracks():
        title = "release-%s-gc" % track
        s = {
            "_id": str(uuid.uuid4()),
            "_type": "visualization",
            "_source": {
                "title": title,
                "visState": "{\"title\":\"%s\",\"type\":\"histogram\",\"params\":{\"addLegend\":true,\"addTimeMarker\":false,\"addTooltip\":true,\"categoryAxes\":[{\"id\":\"CategoryAxis-1\",\"labels\":{\"show\":true,\"truncate\":100},\"position\":\"bottom\",\"scale\":{\"type\":\"linear\"},\"show\":true,\"style\":{},\"title\":{\"text\":\"filters\"},\"type\":\"category\"}],\"defaultYExtents\":false,\"drawLinesBetweenPoints\":true,\"grid\":{\"categoryLines\":false,\"style\":{\"color\":\"#eee\"}},\"interpolate\":\"linear\",\"legendPosition\":\"right\",\"radiusRatio\":9,\"scale\":\"linear\",\"seriesParams\":[{\"data\":{\"id\":\"1\",\"label\":\"Total GC Duration [ms]\"},\"drawLinesBetweenPoints\":true,\"mode\":\"stacked\",\"show\":\"true\",\"showCircles\":true,\"type\":\"histogram\",\"valueAxis\":\"ValueAxis-1\"}],\"setYExtents\":false,\"showCircles\":true,\"times\":[],\"valueAxes\":[{\"id\":\"ValueAxis-1\",\"labels\":{\"filter\":false,\"rotate\":0,\"show\":true,\"truncate\":100},\"name\":\"LeftAxis-1\",\"position\":\"left\",\"scale\":{\"mode\":\"normal\",\"type\":\"linear\"},\"show\":true,\"style\":{},\"title\":{\"text\":\"Total GC Duration [ms]\"},\"type\":\"value\"}]},\"aggs\":[{\"id\":\"1\",\"enabled\":true,\"type\":\"median\",\"schema\":\"metric\",\"params\":{\"field\":\"value.single\",\"percents\":[50],\"customLabel\":\"Total GC Duration [ms]\"}},{\"id\":\"2\",\"enabled\":true,\"type\":\"filters\",\"schema\":\"segment\",\"params\":{\"filters\":[{\"input\":{\"query\":{\"query_string\":{\"query\":\"name:young_gc_time\",\"analyze_wildcard\":true}}},\"label\":\"Young GC\"},{\"input\":{\"query\":{\"query_string\":{\"query\":\"name:old_gc_time\",\"analyze_wildcard\":true}}},\"label\":\"Old GC\"}]}},{\"id\":\"3\",\"enabled\":true,\"type\":\"terms\",\"schema\":\"split\",\"params\":{\"field\":\"distribution-version\",\"size\":10,\"order\":\"asc\",\"orderBy\":\"_term\",\"row\":false}},{\"id\":\"4\",\"enabled\":true,\"type\":\"terms\",\"schema\":\"group\",\"params\":{\"field\":\"user-tag\",\"size\":5,\"order\":\"desc\",\"orderBy\":\"_term\"}}],\"listeners\":{}}" % title,
                "uiStateJSON": "{}",
                "description": "",
                "version": 1,
                "kibanaSavedObjectMeta": {
                    "searchSourceJSON": "{\"index\":\"rally-results-*\",\"query\":{\"query_string\":{\"query\":\"environment:release AND active:true AND track:%s AND challenge:%s AND car:%s\",\"analyze_wildcard\":true}},\"filter\":[]}" % (track, challenge, car)
                }
            }
        }
        structures.append(s)

    return structures


def main():
    structures = generate_index_ops() + generate_queries() + generate_io() + generate_gc()
    print(json.dumps(structures, indent=4))


if __name__ == '__main__':
    main()
