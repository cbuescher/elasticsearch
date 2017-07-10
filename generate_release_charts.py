import uuid
import json
import os
import sys


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


def generate_index_ops(tracks):
    def tracks_for_index():
        all_tracks = []
        for track_structure in tracks:
            track = track_structure["track"]
            challenges_of_track = challenges(track)
            for combination in track_structure["combinations"]:
                if combination.get("release-charts", True):
                    challenge = combination["challenge"]
                    car = combination["car"]
                    cci = []
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
            filters = filters + "{\"input\":{\"query\":{\"query_string\":{\"analyze_wildcard\":true,\"query\":\"operation:%s AND challenge:%s AND car:%s\"}}},\"label\":\"%s\"}" % (
            index_op, challenge, car, label)

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
                            "\"style\":{},\"title\":{\"text\":\"Median Indexing Throughput [docs/s]\"},\"type\":\"value\"}]},\"title\":\"%s\",\"type\":\"histogram\"}" % (
                            filters, title),
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


def default_tracks(tracks):
    all_tracks = []
    for track_structure in tracks:
        for combination in track_structure["combinations"]:
            if combination.get("default-combination", False):
                track = track_structure["track"]
                challenge = combination["challenge"]
                car = combination["car"]
                default_challenge = challenges(track)[0]
                # default challenge is usually the first one. No need for complex logic
                assert default_challenge["default"]
                # filter queries
                queries = [t["operation"] for t in default_challenge["schedule"] if
                           not (t["operation"].startswith("index") or t["operation"] in ["force-merge", "node-stats"])]
                all_tracks.append((track, challenge, car, queries))

    return all_tracks


def generate_queries(tracks):
    # output JSON structures
    structures = []
    for track, challenge, car, queries in default_tracks(tracks):
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


def generate_io(tracks):
    # output JSON structures
    structures = []
    for track, challenge, car, queries in default_tracks(tracks):
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
                    "searchSourceJSON": "{\"index\":\"rally-results-*\",\"query\":{\"query_string\":{\"query\":\"environment:release AND active:true AND track:%s AND challenge:%s AND car:%s\",\"analyze_wildcard\":true}},\"filter\":[]}" % (
                    track, challenge, car)
                }
            }
        }
        structures.append(s)

    return structures


def generate_gc(tracks):
    structures = []
    for track, challenge, car, queries in default_tracks(tracks):
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
                    "searchSourceJSON": "{\"index\":\"rally-results-*\",\"query\":{\"query_string\":{\"query\":\"environment:release AND active:true AND track:%s AND challenge:%s AND car:%s\",\"analyze_wildcard\":true}},\"filter\":[]}" % (
                    track, challenge, car)
                }
            }
        }
        structures.append(s)

    return structures


def load_tracks(track_filter):
    import json
    root = os.path.dirname(os.path.realpath(__file__))
    with open("%s/resources/tracks.json" % root, "r") as tracks_file:
        all_tracks = json.load(tracks_file)
    if track_filter:
        return [t for t in all_tracks if t["track"] == track_filter]
    else:
        return all_tracks


def main():
    track_filter = sys.argv[1] if len(sys.argv) > 1 else None
    tracks = load_tracks(track_filter)

    structures = generate_index_ops(tracks) + generate_queries(tracks) + generate_io(tracks) + generate_gc(tracks)
    print(json.dumps(structures, indent=4))


if __name__ == '__main__':
    main()
