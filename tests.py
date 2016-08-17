import datetime
import os
import unittest

if __name__ == "__main__" and __package__ is None:
    __package__ = "night_rally"

import night_rally

EXAMPLE_REPORT = """Metric,Operation,Value,Unit
Indexing time,,0.17859999999999998,min
Refresh time,,0.017216666666666665,min
Merge throttle time,,0.00001,min
Merge time,,0.00002,min
Flush time,,0.00003,min
Median CPU usage,,44.35,%
Total Young Gen GC,,0.183,s
Total Old Gen GC,,0.039,s
Index size,,0.0029572583734989166,GB
Totally written,,0.010284423828125,GB
Heap used for segments,,0.18365955352783203,MB
Heap used for doc values,,0.0374603271484375,MB
Heap used for terms,,0.12516021728515625,MB
Heap used for norms,,0.013427734375,MB
Heap used for points,,0.0015230178833007812,MB
Heap used for stored fields,,0.0060882568359375,MB
Segment count,,20,
Min Throughput,index-append,5397,docs/s
Median Throughput,index-append,5397,docs/s
Max Throughput,index-append,5397,docs/s
50.0th percentile latency,index-append,1207.0007925001391,ms
100th percentile latency,index-append,1667.5097420002203,ms
50.0th percentile service time,index-append,1206.4965629999733,ms
100th percentile service time,index-append,1667.4060969999118,ms
Min Throughput,force-merge,3.584243072470483,ops/s
Median Throughput,force-merge,3.584243072470483,ops/s
Max Throughput,force-merge,3.584243072470483,ops/s
100th percentile latency,force-merge,279.05247299986513,ms
100th percentile service time,force-merge,278.99860500019713,ms
Min Throughput,index-stats,50.464826622932584,ops/s
Median Throughput,index-stats,50.464826622932584,ops/s
Max Throughput,index-stats,50.464826622932584,ops/s
90.0th percentile latency,index-stats,5.99013400033073,ms
99.0th percentile latency,index-stats,8.948227400155709,ms
100th percentile latency,index-stats,10.273481000240281,ms
90.0th percentile service time,index-stats,5.906189000052112,ms
99.0th percentile service time,index-stats,8.886418309989502,ms
100th percentile service time,index-stats,10.212653000053251,ms
Min Throughput,node-stats,50.38507158772506,ops/s
Median Throughput,node-stats,50.38507158772506,ops/s
Max Throughput,node-stats,50.38507158772506,ops/s
90.0th percentile latency,node-stats,7.209921199864766,ms
99.0th percentile latency,node-stats,8.401418720027323,ms
100th percentile latency,node-stats,8.536327999991045,ms
90.0th percentile service time,node-stats,7.029080400025123,ms
99.0th percentile service time,node-stats,8.323224410164585,ms
100th percentile service time,node-stats,8.461765999982163,ms
Min Throughput,default,87.53908674923343,ops/s
Median Throughput,default,87.53908674923343,ops/s
Max Throughput,default,87.53908674923343,ops/s
90.0th percentile latency,default,243.9430980000452,ms
99.0th percentile latency,default,260,ms
100th percentile latency,default,267.8802770001312,ms
90.0th percentile service time,default,7.186231000105181,ms
99.0th percentile service time,default,29.398342300146396,ms
100th percentile service time,default,29.841856000075495,ms
Min Throughput,term,66.06506759059893,ops/s
Median Throughput,term,66.06506759059893,ops/s
Max Throughput,term,66.06506759059893,ops/s
90.0th percentile latency,term,327.4331419997907,ms
99.0th percentile latency,term,362,ms
100th percentile latency,term,375.9342100001959,ms
90.0th percentile service time,term,15.053268499968908,ms
99.0th percentile service time,term,23.72307229970829,ms
100th percentile service time,term,30.869281999912346,ms
Min Throughput,phrase,66.02210910087487,ops/s
Median Throughput,phrase,66.02210910087487,ops/s
Max Throughput,phrase,66.02210910087487,ops/s
90.0th percentile latency,phrase,302.5646285000221,ms
99.0th percentile latency,phrase,327,ms
100th percentile latency,phrase,336.86139700012063,ms
90.0th percentile service time,phrase,13.390509500140979,ms
99.0th percentile service time,phrase,31.721146799827693,ms
100th percentile service time,phrase,34.068470999955025,ms
Min Throughput,country_agg_uncached,5.543029792524617,ops/s
Median Throughput,country_agg_uncached,5.543029792524617,ops/s
Max Throughput,country_agg_uncached,5.543029792524617,ops/s
90.0th percentile latency,country_agg_uncached,4.0779410001050564,ms
99.0th percentile latency,country_agg_uncached,7,ms
100th percentile latency,country_agg_uncached,13.955715000065538,ms
90.0th percentile service time,country_agg_uncached,4.020528999944872,ms
99.0th percentile service time,country_agg_uncached,7.444769800258653,ms
100th percentile service time,country_agg_uncached,13.036161999934848,ms
Min Throughput,country_agg_cached,66.82955881529158,ops/s
Median Throughput,country_agg_cached,66.82955881529158,ops/s
Max Throughput,country_agg_cached,66.82955881529158,ops/s
90.0th percentile latency,country_agg_cached,281.8406309997954,ms
99.0th percentile latency,country_agg_cached,306,ms
100th percentile latency,country_agg_cached,308.8113290000365,ms
90.0th percentile service time,country_agg_cached,12.607392500058268,ms
99.0th percentile service time,country_agg_cached,28.298259399980452,ms
100th percentile service time,country_agg_cached,31.018782999581163,ms
Min Throughput,scroll,68.02185969256655,ops/s
Median Throughput,scroll,68.02185969256655,ops/s
Max Throughput,scroll,68.02185969256655,ops/s
90.0th percentile latency,scroll,310.76915800008464,ms
99.0th percentile latency,scroll,553,ms
100th percentile latency,scroll,609.5207670000491,ms
90.0th percentile service time,scroll,130.94287499984603,ms
99.0th percentile service time,scroll,146.98445310000352,ms
100th percentile service time,scroll,160.21831499983819,ms
Min Throughput,expression,2.217183235794662,ops/s
Median Throughput,expression,2.217183235794662,ops/s
Max Throughput,expression,2.217183235794662,ops/s
90.0th percentile latency,expression,8.30242050005836,ms
99.0th percentile latency,expression,12,ms
100th percentile latency,expression,13.861290000022564,ms
90.0th percentile service time,expression,8.214605000148367,ms
99.0th percentile service time,expression,12.62142459986535,ms
100th percentile service time,expression,13.8114010001118,ms
Min Throughput,painless_static,2.2175969605297623,ops/s
Median Throughput,painless_static,2.2175969605297623,ops/s
Max Throughput,painless_static,2.2175969605297623,ops/s
90.0th percentile latency,painless_static,8.255358500036891,ms
99.0th percentile latency,painless_static,13,ms
100th percentile latency,painless_static,13.705662000120356,ms
90.0th percentile service time,painless_static,8.18714000001819,ms
99.0th percentile service time,painless_static,13.627798499919663,ms
100th percentile service time,painless_static,13.649789999817585,ms"""


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
        night_rally._run_rally(start_date, tracks, system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --configuration-name=nightly --pipeline=from-sources-complete --quiet --revision \"@2016-01-01T00:00:00Z\" "
                "--effective-start-date \"2016-01-01 00:00:00\" --track=geonames --challenge=append-no-conflicts --car=defaults "
                "--report-format=csv "
                "--report-file=%s/.rally/benchmarks/reports/rally/2016-01-01-00-00-00/geonames/append-no-conflicts/defaults/report.csv"
                % os.getenv("HOME"),
                "rally --configuration-name=nightly --pipeline=from-sources-skip-build --quiet --revision \"@2016-01-01T00:00:00Z\" "
                "--effective-start-date \"2016-01-01 00:00:00\" --track=geonames --challenge=append-no-conflicts --car=4gheap "
                "--report-format=csv "
                "--report-file=%s/.rally/benchmarks/reports/rally/2016-01-01-00-00-00/geonames/append-no-conflicts/4gheap/report.csv"
                % os.getenv("HOME")]
            ,
            system_call.calls
        )

    def test_run_two_tracks_successfully(self):
        system_call = RecordingSystemCall(return_value=False)

        tracks = {"geonames": [
            ["append-no-conflicts", "defaults"],
        ],
            "percolator": [
                ["append-no-conflicts", "4gheap"],
            ]
        }
        start_date = datetime.datetime(2016, 10, 1)
        night_rally._run_rally(start_date, tracks, system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --configuration-name=nightly --pipeline=from-sources-complete --quiet --revision \"@2016-10-01T00:00:00Z\" "
                "--effective-start-date \"2016-10-01 00:00:00\" --track=geonames --challenge=append-no-conflicts --car=defaults "
                "--report-format=csv "
                "--report-file=%s/.rally/benchmarks/reports/rally/2016-10-01-00-00-00/geonames/append-no-conflicts/defaults/report.csv"
                % os.getenv("HOME"),
                "rally --configuration-name=nightly --pipeline=from-sources-skip-build --quiet --revision \"@2016-10-01T00:00:00Z\" "
                "--effective-start-date \"2016-10-01 00:00:00\" --track=percolator --challenge=append-no-conflicts --car=4gheap "
                "--report-format=csv "
                "--report-file=%s/.rally/benchmarks/reports/rally/2016-10-01-00-00-00/percolator/append-no-conflicts/4gheap/report.csv"
                % os.getenv("HOME")]
            ,
            system_call.calls
        )

    def test_run_continues_on_error(self):
        system_call = RecordingSystemCall(return_value=True)

        tracks = {"geonames": [
            ["append-no-conflicts", "defaults"],
        ],
            "percolator": [
                ["append-no-conflicts", "4gheap"],
            ]
        }
        start_date = datetime.datetime(2016, 10, 1)
        night_rally._run_rally(start_date, tracks, system_call)
        self.assertEqual(2, len(system_call.calls))
        self.assertEqual(
            [
                "rally --configuration-name=nightly --pipeline=from-sources-complete --quiet --revision \"@2016-10-01T00:00:00Z\" "
                "--effective-start-date \"2016-10-01 00:00:00\" --track=geonames --challenge=append-no-conflicts --car=defaults "
                "--report-format=csv "
                "--report-file=%s/.rally/benchmarks/reports/rally/2016-10-01-00-00-00/geonames/append-no-conflicts/defaults/report.csv"
                % os.getenv("HOME"),
                "rally --configuration-name=nightly --pipeline=from-sources-skip-build --quiet --revision \"@2016-10-01T00:00:00Z\" "
                "--effective-start-date \"2016-10-01 00:00:00\" --track=percolator --challenge=append-no-conflicts --car=4gheap "
                "--report-format=csv "
                "--report-file=%s/.rally/benchmarks/reports/rally/2016-10-01-00-00-00/percolator/append-no-conflicts/4gheap/report.csv"
                % os.getenv("HOME")]
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
        self.assertEqual("8.948227400155709", metrics["latency_indices_stats_p99"])
        self.assertEqual("8.401418720027323", metrics["latency_nodes_stats_p99"])
        self.assertEqual(["260", "362", "327", "7", "306", "553", "12", "13"], metrics["query_latency_p99"])


if __name__ == '__main__':
    unittest.main()
