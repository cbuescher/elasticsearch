import collections
import datetime
import unittest

if __name__ == "__main__" and __package__ is None:
    __package__ = "night_rally"

import night_rally

EXAMPLE_REPORT = """Lap,Metric,Operation,Value,Unit
All,Indexing time,,0.17859999999999998,min
All,Refresh time,,0.017216666666666665,min
All,Merge throttle time,,0.00001,min
All,Merge time,,0.00002,min
All,Flush time,,0.00003,min
All,Merge time (postings),,1.8252,min
All,Merge time (stored fields),,0.7546166666666667,min
All,Merge time (doc values),,1.5041166666666668,min
All,Merge time (norms),,0.14778333333333335,min
All,Merge time (points),,0.26083333333333336,min
All,Median CPU usage,,44.35,%
All,Total Young Gen GC,,0.183,s
All,Total Old Gen GC,,0.039,s
All,Index size,,0.0029572583734989166,GB
All,Totally written,,0.010284423828125,GB
All,Heap used for segments,,0.18365955352783203,MB
All,Heap used for doc values,,0.0374603271484375,MB
All,Heap used for terms,,0.12516021728515625,MB
All,Heap used for norms,,0.013427734375,MB
All,Heap used for points,,0.0015230178833007812,MB
All,Heap used for stored fields,,0.0060882568359375,MB
All,Segment count,,20,
All,Min Throughput,index-append,5397,docs/s
All,Median Throughput,index-append,5397,docs/s
All,Max Throughput,index-append,5397,docs/s
All,50.0th percentile latency,index-append,1207.0007925001391,ms
All,100th percentile latency,index-append,1667.5097420002203,ms
All,50.0th percentile service time,index-append,1206.4965629999733,ms
All,100th percentile service time,index-append,1667.4060969999118,ms
All,Min Throughput,force-merge,3.584243072470483,ops/s
All,Median Throughput,force-merge,3.584243072470483,ops/s
All,Max Throughput,force-merge,3.584243072470483,ops/s
All,100th percentile latency,force-merge,279.05247299986513,ms
All,100th percentile service time,force-merge,278.99860500019713,ms
All,Min Throughput,index-stats,50.464826622932584,ops/s
All,Median Throughput,index-stats,50.464826622932584,ops/s
All,Max Throughput,index-stats,50.464826622932584,ops/s
All,90.0th percentile latency,index-stats,5.99013400033073,ms
All,99.0th percentile latency,index-stats,8.948227400155709,ms
All,100th percentile latency,index-stats,10.273481000240281,ms
All,90.0th percentile service time,index-stats,5.906189000052112,ms
All,99.0th percentile service time,index-stats,8.886418309989502,ms
All,100th percentile service time,index-stats,10.212653000053251,ms
All,Min Throughput,node-stats,50.38507158772506,ops/s
All,Median Throughput,node-stats,50.38507158772506,ops/s
All,Max Throughput,node-stats,50.38507158772506,ops/s
All,90.0th percentile latency,node-stats,7.209921199864766,ms
All,99.0th percentile latency,node-stats,8.401418720027323,ms
All,100th percentile latency,node-stats,8.536327999991045,ms
All,90.0th percentile service time,node-stats,7.029080400025123,ms
All,99.0th percentile service time,node-stats,8.323224410164585,ms
All,100th percentile service time,node-stats,8.461765999982163,ms
All,Min Throughput,default,87.53908674923343,ops/s
All,Median Throughput,default,87.53908674923343,ops/s
All,Max Throughput,default,87.53908674923343,ops/s
All,90.0th percentile latency,default,243.9430980000452,ms
All,99.0th percentile latency,default,260,ms
All,100th percentile latency,default,267.8802770001312,ms
All,90.0th percentile service time,default,7.186231000105181,ms
All,99.0th percentile service time,default,29,ms
All,100th percentile service time,default,29.841856000075495,ms
All,Min Throughput,term,66.06506759059893,ops/s
All,Median Throughput,term,66.06506759059893,ops/s
All,Max Throughput,term,66.06506759059893,ops/s
All,90.0th percentile latency,term,327.4331419997907,ms
All,99.0th percentile latency,term,362,ms
All,100th percentile latency,term,375.9342100001959,ms
All,90.0th percentile service time,term,15.053268499968908,ms
All,99.0th percentile service time,term,23,ms
All,100th percentile service time,term,30.869281999912346,ms
All,Min Throughput,phrase,66.02210910087487,ops/s
All,Median Throughput,phrase,66.02210910087487,ops/s
All,Max Throughput,phrase,66.02210910087487,ops/s
All,90.0th percentile latency,phrase,302.5646285000221,ms
All,99.0th percentile latency,phrase,327,ms
All,100th percentile latency,phrase,336.86139700012063,ms
All,90.0th percentile service time,phrase,13.390509500140979,ms
All,99.0th percentile service time,phrase,31,ms
All,100th percentile service time,phrase,34.068470999955025,ms
All,Min Throughput,country_agg_uncached,5.543029792524617,ops/s
All,Median Throughput,country_agg_uncached,5.543029792524617,ops/s
All,Max Throughput,country_agg_uncached,5.543029792524617,ops/s
All,90.0th percentile latency,country_agg_uncached,4.0779410001050564,ms
All,99.0th percentile latency,country_agg_uncached,7,ms
All,100th percentile latency,country_agg_uncached,13.955715000065538,ms
All,90.0th percentile service time,country_agg_uncached,4.020528999944872,ms
All,99.0th percentile service time,country_agg_uncached,7,ms
All,100th percentile service time,country_agg_uncached,13.036161999934848,ms
All,Min Throughput,country_agg_cached,66.82955881529158,ops/s
All,Median Throughput,country_agg_cached,66.82955881529158,ops/s
All,Max Throughput,country_agg_cached,66.82955881529158,ops/s
All,90.0th percentile latency,country_agg_cached,281.8406309997954,ms
All,99.0th percentile latency,country_agg_cached,306,ms
All,100th percentile latency,country_agg_cached,308.8113290000365,ms
All,90.0th percentile service time,country_agg_cached,12.607392500058268,ms
All,99.0th percentile service time,country_agg_cached,28,ms
All,100th percentile service time,country_agg_cached,31.018782999581163,ms
All,Min Throughput,scroll,68.02185969256655,ops/s
All,Median Throughput,scroll,68.02185969256655,ops/s
All,Max Throughput,scroll,68.02185969256655,ops/s
All,90.0th percentile latency,scroll,310.76915800008464,ms
All,99.0th percentile latency,scroll,553,ms
All,100th percentile latency,scroll,609.5207670000491,ms
All,90.0th percentile service time,scroll,130.94287499984603,ms
All,99.0th percentile service time,scroll,146,ms
All,100th percentile service time,scroll,160.21831499983819,ms
All,Min Throughput,expression,2.217183235794662,ops/s
All,Median Throughput,expression,2.217183235794662,ops/s
All,Max Throughput,expression,2.217183235794662,ops/s
All,90.0th percentile latency,expression,8.30242050005836,ms
All,99.0th percentile latency,expression,12,ms
All,100th percentile latency,expression,13.861290000022564,ms
All,90.0th percentile service time,expression,8.214605000148367,ms
All,99.0th percentile service time,expression,12,ms
All,100th percentile service time,expression,13.8114010001118,ms
All,Min Throughput,painless_static,2.2175969605297623,ops/s
All,Median Throughput,painless_static,2.2175969605297623,ops/s
All,Max Throughput,painless_static,2.2175969605297623,ops/s
All,90.0th percentile latency,painless_static,8.255358500036891,ms
All,99.0th percentile latency,painless_static,13,ms
All,100th percentile latency,painless_static,13.705662000120356,ms
All,90.0th percentile service time,painless_static,8.18714000001819,ms
All,99.0th percentile service time,painless_static,13,ms
All,100th percentile service time,painless_static,13.649789999817585,ms"""

EXAMPLE_META_REPORT = """Name,Value
Elasticsearch source revision,247cafe"""


class RecordingSystemCall:
    def __init__(self, return_value):
        self.calls = []
        self.return_value = return_value

    def __call__(self, *args, **kwargs):
        self.calls.append(*args)
        return self.return_value


class NightRallyTests(unittest.TestCase):
    def test_run_two_challenges_successfully(self):
        system_call = RecordingSystemCall(return_value=False)

        tracks = {"geonames": [
            ["append-no-conflicts", "defaults"],
            ["append-no-conflicts", "4gheap"]
        ]}
        start_date = datetime.datetime(2016, 1, 1)
        cmd = night_rally.NightlyCommand(start_date, "localhost", "/rally_root")
        night_rally.run_rally(tracks, cmd, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --configuration-name=nightly --target-host=localhost --pipeline=from-sources-complete --quiet "
                "--revision \"@2016-01-01T00:00:00Z\" --effective-start-date \"2016-01-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=defaults --report-format=csv "
                "--report-file=/rally_root/reports/rally/2016-01-01-00-00-00/geonames/append-no-conflicts/defaults/report.csv",

                "rally --configuration-name=nightly --target-host=localhost --pipeline=from-sources-skip-build --quiet "
                "--revision \"@2016-01-01T00:00:00Z\" --effective-start-date \"2016-01-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=4gheap --report-format=csv "
                "--report-file=/rally_root/reports/rally/2016-01-01-00-00-00/geonames/append-no-conflicts/4gheap/report.csv"
                ]
            ,
            system_call.calls
        )

    def test_run_two_tracks_successfully(self):
        system_call = RecordingSystemCall(return_value=False)

        tracks = collections.OrderedDict()
        tracks["geonames"] = [["append-no-conflicts", "defaults"]]
        tracks["percolator"] = [["append-no-conflicts", "4gheap"]]

        start_date = datetime.datetime(2016, 10, 1)
        cmd = night_rally.NightlyCommand(start_date, "localhost", "/rally_root", override_src_dir="~/src/")
        night_rally.run_rally(tracks, cmd, system=system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --configuration-name=nightly --target-host=localhost --pipeline=from-sources-complete --quiet "
                "--revision \"@2016-10-01T00:00:00Z\" --effective-start-date \"2016-10-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=defaults --report-format=csv "
                "--report-file=/rally_root/reports/rally/2016-10-01-00-00-00/geonames/append-no-conflicts/defaults/report.csv "
                "--override-src-dir=~/src/",
                "rally --configuration-name=nightly --target-host=localhost --pipeline=from-sources-skip-build --quiet "
                "--revision \"@2016-10-01T00:00:00Z\" --effective-start-date \"2016-10-01 00:00:00\" --track=percolator "
                "--challenge=append-no-conflicts --car=4gheap --report-format=csv "
                "--report-file=/rally_root/reports/rally/2016-10-01-00-00-00/percolator/append-no-conflicts/4gheap/report.csv "
                "--override-src-dir=~/src/"]
            ,
            system_call.calls
        )

    def test_run_continues_on_error(self):
        self.maxDiff = None
        system_call = RecordingSystemCall(return_value=True)

        tracks = collections.OrderedDict()
        tracks["geonames"] = [["append-no-conflicts", "defaults"]]
        tracks["percolator"] = [["append-no-conflicts", "4gheap"]]

        start_date = datetime.datetime(2016, 10, 1)
        cmd = night_rally.NightlyCommand(start_date, "localhost", "/rally_root")
        night_rally.run_rally(tracks, cmd, system=system_call)

        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --configuration-name=nightly --target-host=localhost --pipeline=from-sources-complete --quiet "
                "--revision \"@2016-10-01T00:00:00Z\" --effective-start-date \"2016-10-01 00:00:00\" --track=geonames "
                "--challenge=append-no-conflicts --car=defaults --report-format=csv "
                "--report-file=/rally_root/reports/rally/2016-10-01-00-00-00/geonames/append-no-conflicts/defaults/report.csv",
                "rally --configuration-name=nightly --target-host=localhost --pipeline=from-sources-skip-build --quiet "
                "--revision \"@2016-10-01T00:00:00Z\" --effective-start-date \"2016-10-01 00:00:00\" --track=percolator "
                "--challenge=append-no-conflicts --car=4gheap --report-format=csv "
                "--report-file=/rally_root/reports/rally/2016-10-01-00-00-00/percolator/append-no-conflicts/4gheap/report.csv"]
            ,
            system_call.calls
        )

    def test_extract_metrics(self):
        metrics = night_rally.extract_metrics(EXAMPLE_REPORT.split("\n"))

        self.assertEqual("5397", metrics["median_indexing_throughput"])
        self.assertEqual("0.183", metrics["young_gen_gc"])
        self.assertEqual("0.039", metrics["old_gen_gc"])
        self.assertEqual("0.17859999999999998", metrics["indexing_time"])
        self.assertEqual("0.017216666666666665", metrics["refresh_time"])
        self.assertEqual("0.00003", metrics["flush_time"])
        self.assertEqual("0.00001", metrics["merge_throttle_time"])
        self.assertEqual("0.00002", metrics["merge_time"])
        self.assertEqual("20", metrics["segment_count"])
        self.assertEqual("0.0029572583734989166", metrics["index_size"])
        self.assertEqual("0.010284423828125", metrics["totally_written"])
        self.assertEqual("0.18365955352783203", metrics["mem_segments"])
        self.assertEqual("0.0374603271484375", metrics["mem_doc_values"])
        self.assertEqual("0.12516021728515625", metrics["mem_terms"])
        self.assertEqual("0.013427734375", metrics["mem_norms"])
        self.assertEqual("0.0015230178833007812", metrics["mem_points"])
        self.assertEqual("0.0060882568359375", metrics["mem_fields"])
        self.assertEqual("8.886418309989502", metrics["latency_indices_stats_p99"])
        self.assertEqual("8.323224410164585", metrics["latency_nodes_stats_p99"])
        self.assertEqual(["29", "23", "31", "7", "28", "146", "12", "13"], metrics["query_latency_p99"])

    def test_extract_meta_metrics(self):
        metrics = night_rally.extract_meta_metrics(EXAMPLE_META_REPORT.split("\n"))
        self.assertEqual("247cafe", metrics["source_revision"])

    def test_insert_new_master_record(self):
        self.assertEqual(["Header", "5.2.0,1111", "master,1.00"],
                         night_rally.insert(["Header", "5.2.0,1111"], "master", "master", "1.00"))

    def test_override_existing_master_record(self):
        self.assertEqual(["Header", "5.2.0,1111", "master,1.00"],
                         night_rally.insert(["Header", "5.2.0,1111", "master,3.4"], "master", "master", "1.00"))

if __name__ == '__main__':
    unittest.main()
