**New here? Please check our [benchmark one stop page](42.md) which should answer most of your questions.**

## Night Rally

Night Rally is a set of driver scripts for [running nightly macrobenchmarks for Elasticsearch](https://elasticsearch-ci.elastic.co/view/All/job/elastic+elasticsearch+master+macrobenchmark-periodic) and [publishing the results](https://elasticsearch-benchmarks.elastic.co/). The macrobenchmarks themselves are executed by [Rally](https://github.com/elastic/rally).

### Prerequisites

* Python 3.4+ available as `python3` on the path (verify with: `python3 --version` which should print `Python 3.4.0` (or higher))
* `pip3` available on the path (verify with `pip3 --version`)
* `awscli` available on the command line and properly set up to write to the bucket `s3://elasticsearch-benchmarks.elasticsearch.org`.
* `Ansible` available on the command line (only needed in our nightly benchmarking environment)
* All prerequisites for [Rally](https://github.com/elastic/rally)

Night Rally is only tested on Mac OS X and Linux.

### Getting Started

1. Clone this repo: `git clone git@github.com:elastic/night-rally.git`
2. Ensure that all prerequisites of [Rally](https://github.com/elastic/rally) are properly setup. Hint. It is *not* required to install Rally manually. Just ensure that its prerequisites are installed.

Now you can invoke Night Rally regularly with the startup script `night_rally.sh` e.g. via cron. The script can also self-update if invoked as `night_rally.sh --self-update`. 


### How do I ...?

#### Add an annotation

To add an annotation, use the admin tool. First find the correct trial timestamp by issuing `python3 admin.py list races --environment=nightly`. You will need the trial timestamp later. Below are examples for common cases:
 
* Add an annotation for all charts for a specific nightly benchmark trial: `python3 admin.py add annotation --environment=nightly --trial-timestamp=20170502T220213Z --message="Just a test annotation"`
* Add an annotation for all charts of one track for a specific nightly benchmark trial: `python3 admin.py add annotation --environment=nightly --trial-timestamp=20170502T220213Z --track=geonames --message="Just a test annotation for geonames"`
* Add an annotation for a specific chart of one track for a specific nightly benchmark trial: `python3 admin.py add annotation --environment=nightly --trial-timestamp=20170502T220213Z --track=geonames --chart=io --message="Just a test annotation"`

For more details, please issue `python3 admin.py add annotation --help`.

**Note:** The admin tool also supports a dry-run mode for all commands that would change the data store. Just append `--dry-run`.

**Note:** The new annotation will show up immediately. 

#### Remove an annotation

If you have made an error you can also remove specific annotations by id.

1. Issue `python3 admin.py list annotations --environment=nightly` and find the right annotation. Note that only the 20 most recent annotations are shown. You can show more, by specifying `--limit=NUMBER`. 
2. Suppose the id of the annotation that we want to delete is `AVwM0jAA-dI09MVLDV39`. Then issue `python3 admin.py delete annotation --id=AVwM0jAA-dI09MVLDV39`.

For more details, please issue `python3 admin.py delete annotation --help`.

**Note:** The admin tool also supports a dry-run mode for all commands that would change the data store. Just append `--dry-run`.
 
#### Add a new track
 
The following steps are necessary to add a new track: 

1. Add your track and the challenges to run in `resources/track.json`
2. Create nightly and release charts and the corresponding dashboards on the Kibana instance https://ece78408d8df7290d4ad6e3ffac5af6a.us-east-1.aws.found.io (it's mapped to be publicly reachable). You can generate release charts with `python3 generate_release_charts.py YOUR_TRACK_NAME`. At the moment there is no such generator for nightly charts though.
3. Copy a directory in `external/pages`, adjust the names accordingly and reference the UUID of the dashboards that you've created in step 2.
4. Adjust the menu structure in all other files (if this happens more often, we should think about using a template engine for that...)

If you're finished, please submit a PR. After the PR is merged, the new track will show up after the next benchmark.


#### Run a release benchmark

Suppose we want to publish a new release benchmark of the Elasticsearch release `5.3.1` on our benchmark page. To do that, start a new [macrobenchmark build](https://elasticsearch-ci.elastic.co/view/All/job/elastic+elasticsearch+master+macrobenchmark-periodic/) with the following parameters:

* `MODE`: `release`
* `RELEASE`: `5.3.1`
* `TARGET_HOST`: Just use the default value

The results will show up automatically as soon as the build is finished.

#### Run an ad-hoc benchmark

_Note: An ad-hoc benchmark is a benchmark of an arbitrary git commit hash that should be published as a separate data series in our release comparison charts._

Suppose we want to publish the results of the commit hash `66202dc` in the Elasticsearch repo as "Lucene 7 upgrade" on our benchmark page. 

1. Add "Lucene 7 upgrade" to the `versions` array in each `index.html` in `external/pages`. Commit and push your changes.
2. On the benchmark machine, issue the following command:

```
night_rally.sh --target-host=target-551504.benchmark.hetzner-dc17.elasticnet.co:39200 --mode=adhoc --revision=66202dc --release="Lucene 7"
```