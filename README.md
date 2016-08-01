## Night Rally

Night Rally is a set of driver scripts for running nightly macrobenchmarks for Elasticsearch. The macrobenchmarks themselves are executed by [Rally](https://github.com/elastic/rally).

### Prerequisites

* Python 3.4+ available as `python3` on the path (verify with: `python3 --version` which should print `Python 3.4.0` (or higher))
* `pip3` available on the path (verify with `pip3 --version`)
* `s3cmd` available on the command line and properly set up to write to the bucket `s3://elasticsearch-benchmarks.elasticsearch.org`.
* All prerequisites for [Rally](https://github.com/elastic/rally)

Night Rally is only tested on Mac OS X and Linux.

### Getting Started

1. Clone this repo: `git clone git@github.com:elastic/night-rally.git`
2. Ensure that all prerequisites of [Rally](https://github.com/elastic/rally) are properly setup. Hint. It is *not* required to install Rally manually. Just ensure that its prerequisites are installed.

Now you can invoke night_rally regularly with the startup script `night_rally.sh` e.g. via cron. The script can also self-update if invoked as `night_rally.sh --self-update`. 
