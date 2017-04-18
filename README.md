## Night Rally

Night Rally is a set of driver scripts for [running nightly macrobenchmarks for Elasticsearch](https://elasticsearch-ci.elastic.co/view/All/job/elastic+elasticsearch+master+macrobenchmark-periodic). The macrobenchmarks themselves are executed by [Rally](https://github.com/elastic/rally) and [publishing the results](https://elasticsearch-benchmarks.elastic.co/).

### Prerequisites

* Python 3.4+ available as `python3` on the path (verify with: `python3 --version` which should print `Python 3.4.0` (or higher))
* `pip3` available on the path (verify with `pip3 --version`)
* `awscli` available on the command line and properly set up to write to the bucket `s3://elasticsearch-benchmarks.elasticsearch.org`.
* All prerequisites for [Rally](https://github.com/elastic/rally)

Night Rally is only tested on Mac OS X and Linux.

### Getting Started

1. Clone this repo: `git clone git@github.com:elastic/night-rally.git`
2. Ensure that all prerequisites of [Rally](https://github.com/elastic/rally) are properly setup. Hint. It is *not* required to install Rally manually. Just ensure that its prerequisites are installed.

Now you can invoke night_rally regularly with the startup script `night_rally.sh` e.g. via cron. The script can also self-update if invoked as `night_rally.sh --self-update`. 


### How do I ...?

#### Add an annotation

To add an annotation, just find the right `*_annotation.json` file and add an annotation there. Here is an example record:

```json
{
    "series": "GC young gen (sec)",
    "x": "2016-08-08 06:10:01",
    "shortText": "A",
    "text": "Use 4GB heap instead of default"
}
```

* The series name has to match the series name in the CSV data file on the server (if no example is in the file you want to edit, inspect the S3 bucket `elasticsearch-benchmarks.elastic.co`).
* In `x` you specify the timestamp where an annotation should appear. The timestamp format must be identical to the one in the example.
* `shortText` is the annotation label.
* `text` is the explanation that will be shown in the tooltip for this annotation.

If you're finished, commit and push the change to `master` and the annotation will be shown after the next benchmark run.
 
#### Add a new track
 
For this three steps are needed:

1. Copy a directory in `external/pages` and adjust the names accordingly.
2. Adjust the menu structure in all other files (if this happens more often, we should think about using a template engine for that...)
3. Add your track and the challenges to run in the `tracks` hash in `night_rally.py`

If you're finished, please submit a PR. After the PR is merged, the new track will show up after the next benchmark.


#### Run a release benchmark

Suppose we want to replace the (already published) results of the Elasticsearch release `5.3.0` with release `5.3.1` on our benchmark page. 

1. Replace "5.3.0" with "5.3.1" in the `versions` array in each `index.html` in `external/pages`. Commit and push your changes (commit message convention: "Update comparison charts to 5.3.1")
2. On the benchmark machine, issue the following command:

```
night_rally.sh --target-host=target-551504.benchmark.hetzner-dc17.elasticnet.co:39200 --mode=comparison --release="5.3.1" --replace-release="5.3.0"
```

#### Run an ad-hoc benchmark

_Note: An ad-hoc benchmark is a benchmark of an arbitrary git commit hash that should be published as a separate data series in our release comparison charts._

Suppose we want to publish the results of the commit hash `66202dc` in the Elasticsearch repo as "Lucene 7 upgrade" on our benchmark page. 

1. Add "Lucene 7 upgrade" to the `versions` array in each `index.html` in `external/pages`. Commit and push your changes.
2. On the benchmark machine, issue the following command:

```
night_rally.sh --target-host=target-551504.benchmark.hetzner-dc17.elasticnet.co:39200 --mode=adhoc --revision=66202dc --release="Lucene 7" --replace-release="Lucene 7
```