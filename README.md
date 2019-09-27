**New here? Please check our [benchmark one stop page](42.md) which should answer most of your questions.**

## Night Rally

Night Rally is a set of driver scripts for [running nightly macrobenchmarks for Elasticsearch](https://elasticsearch-ci.elastic.co/view/All/job/elastic+elasticsearch+master+macrobenchmark-periodic) and [publishing the results](https://elasticsearch-benchmarks.elastic.co/). The macrobenchmarks themselves are executed by [Rally](https://github.com/elastic/rally).

### Prerequisites

* Python 3.5+ available as `python3` on the path (verify with: `python3 --version` which should print `Python 3.5.0` (or higher))
* `pip3` available on the path (verify with `pip3 --version`)
* `awscli` available on the command line and properly set up to write to the bucket `s3://elasticsearch-benchmarks.elasticsearch.org`.
* `Ansible` available on the command line (only needed in our nightly benchmarking environment)
* All prerequisites for [Rally](https://github.com/elastic/rally)

Night Rally is only tested on Mac OS X and Linux.

### Getting Started

1. Ensure that all prerequisites of [Rally](https://github.com/elastic/rally) are properly setup. Hint. It is *not* required to install Rally manually. Just ensure that its prerequisites are installed.
2. Clone this repo: `git clone git@github.com:elastic/night-rally.git`
3. [Setup Vault](https://github.com/elastic/infra/blob/master/docs/vault.md)
4. Create a virtualenv with `python3 -m venv .venv` and activate it with `./.venv/bin/activate`
5. Run `make install`

Now you can invoke Night Rally regularly with the startup script `night_rally.sh` e.g. via cron. The script can also self-update if invoked as `night_rally.sh --self-update`.


### How do I ...?

**Note**: Before you issue any command, activate the virtualenv with `./.venv/bin/activate`.

#### Compare what has changed in Elasticsearch between two benchmarks

Find the relevant revision One possibility is to run e.g. `night-rally-admin list races --environment=nightly --track=geonames --challenge=append-no-conflicts` which provides the following list:

```
Race Timestamp    Track     Challenge            Car           Version       Revision    User Tags
----------------  --------  -------------------  ------------  ------------  ----------  -------------------------------------------------------------
20180219T183731Z  geonames  append-no-conflicts  ['defaults']  7.0.0-alpha1  ff2164c     env=bare, name=geonames-append-defaults-1node
20180219T183731Z  geonames  append-no-conflicts  ['defaults']  7.0.0-alpha1  ff2164c     env=bare, name=geonames-append-defaults-x-pack-security-1node
20180218T182130Z  geonames  append-no-conflicts  ['defaults']  7.0.0-alpha1  df07943     env=bare, name=geonames-append-defaults-1node
...
```

You can see the revisions `df07943` and `ff2164c`. If you want to see which commits are included in between, open the Github compare view with https://github.com/elastic/elasticsearch/compare/df07943...ff2164c.


#### Add an annotation

To add an annotation, use the admin tool. First find the correct trial timestamp by issuing `night-rally-admin list races --environment=nightly`. You will need the trial timestamp later. Below are examples for common cases:

* Add an annotation for all charts for a specific nightly benchmark trial: `night-rally-admin add annotation --environment=nightly --trial-timestamp=20170502T220213Z --message="Just a test annotation"`
* Add an annotation for all charts of one track for a specific nightly benchmark trial: `night-rally-admin add annotation --environment=nightly --trial-timestamp=20170502T220213Z --track=geonames --message="Just a test annotation for geonames"`
* Add an annotation for a specific chart of one track for a specific nightly benchmark trial: `night-rally-admin add annotation --environment=nightly --trial-timestamp=20170502T220213Z --track=geonames --chart=io --message="Just a test annotation"`

For more details, please issue `night-rally-admin add annotation --help`.

**Note:** The admin tool also supports a dry-run mode for all commands that would change the data store. Just append `--dry-run`.

**Note:** The new annotation will show up immediately.

#### Remove an annotation

If you have made an error you can also remove specific annotations by id.

1. Issue `night-rally-admin list annotations --environment=nightly` and find the right annotation. Note that only the 20 most recent annotations are shown. You can show more, by specifying `--limit=NUMBER`.
2. Suppose the id of the annotation that we want to delete is `AVwM0jAA-dI09MVLDV39`. Then issue `night-rally-admin delete annotation --id=AVwM0jAA-dI09MVLDV39`.

For more details, please issue `night-rally-admin delete annotation --help`.

**Note:** The admin tool also supports a dry-run mode for all commands that would change the data store. Just append `--dry-run`.

#### Add a new track

Benchmarks get executed in two environments, group-1 / group-2 (see [infra repo](https://github.com/elastic/infra/blob/master/ansible/inventory/production/hetzner/benchmarks)).

The following steps are necessary to add a new track:

1. Add your track and the challenges to run in `resources/race-configs-group-1.json` or `resources/race-configs-group-2.json`.
2. Generate nightly charts and the corresponding dashboards with Rally: `esrally --configuration-name=nightly generate charts --chart-spec-path=$NIGHT_RALLY_HOME/night_rally/resources/race-configs-group*json --chart-type=time-series --output-path=nightly-charts.json`
3. Generate release charts and the corresponding dashboard with Rally: `esrally --configuration-name=release generate charts --chart-spec-path=$NIGHT_RALLY_HOME/night_rally/resources/race-configs-group*json --chart-type=bar --output-path=release-charts.json`
4. Import the new charts to the corresponding dashboards on the [Kibana instance](https://ae582947d1ed4df0adc39c2d047e051a.eu-central-1.aws.cloud.es.io) (it's mapped to be publicly reachable). Please import only the charts for the new track and skip any existing ones.
5. Add the name of your track and the UUIDs of the dashboards that you've created in step two and three to the array at the bottom of `external/pages/index.html`.

If you're finished, please submit a PR. After the PR is merged, we will deploy the new page using the script in `external/pages/deploy.sh` and the dashboards for the new track will show up immediately.

#### Run a release benchmark

Suppose we want to publish a new release benchmark of the Elasticsearch release `6.6.1` on our benchmark page. To do that, start two jobs:

- [target group-1 macrobenchmark build](https://elasticsearch-ci.elastic.co/view/All/job/elastic+elasticsearch+master+macrobenchmark-periodic-group-1/)
- [target group-2 macrobenchmark build](https://elasticsearch-ci.elastic.co/view/All/job/elastic+elasticsearch+master+macrobenchmark-periodic-group-2/)

* `MODE`: `release`
* `RELEASE_LICENSE`: `oss` (default)
* `VERSION`: `6.6.1`

The results will show up automatically as soon as the build is finished.

#### Developing Night Rally / Rally

To verify changes in the Night Rally repo (e.g. in race-configs) or changes in Rally itself that could potentially affect scheduled benchmarks, you are encouraged to use the Vagrant workflow.
It will spin up 4 vm and requires at minimum 21GB of RAM (each target node uses 5GB ram, load driver 1GB). This configuration supports only release benchmarks, as nightlies require java11 and more RAM; read below on how to iterate on nightlies.
Rally will run in [test mode](https://esrally.readthedocs.io/en/stable/command_line_reference.html?highlight=test-mode#test-mode) so the whole run will take just a few minutes.

##### Iterating on release benchmarks while testing changes to night-rally

1. `cd night_rally/fixtures/ansible`
2. `vagrant up`
3. `vagrant ssh /coord/` # ssh'es to the coordinating node
4. `./update_jenkins_night_rally.sh` # rsyncs night_rally to the jenkins user
5. `sudo -iu jenkins`
6. Take a look at `./test_release.sh` before running it; you can specify the corresponding options that would be defined by JJB e.g. mode="release:x-pack"

Results will be sent to the Elastic Cloud cluster `night-rally-tests` (details in LastPass).

To iterate on changes, always remember to re-run `./update_jenkins_night_rally.sh` as user `vagrant`, before re-running tests.

##### Iterating on nightly benchmarks while testing changes to night-rally

1. `cd night_rally/fixtures/ansible`
2. Specify the following environment variables:
    ```
    export VAGRANT_TARGET_MEMORY=7168
    export VAGRANT_ENABLE_BUILD=true
    ```
    
    The reason for increasing memory for the target-nodes is that the additional build step, enabled with `VAGRANT_ENABLE_BUILD`, requires additional memory.)
3. `vagrant up`
4. `vagrant ssh /coord/` # ssh'es to the coordinating node
5. `./update_jenkins_night_rally.sh` # rsyncs night_rally to the jenkins user
6. `sudo -iu jenkins`
7. Run `./test_nightly.sh`

To iterate on changes, always remember to re-run `./update_jenkins_night_rally.sh` as user `vagrant`, before re-running tests.

##### Iterating on long-running benchmarks while testing changes to night-rally

1. `cd night_rally/fixtures/ansible`
2. Specify the following environment variables:
    ```
    # long-running benchmarks run with 8GB of heap
    export VAGRANT_TARGET_MEMORY=10240
    export VAGRANT_ENABLE_BUILD=true
    ```
3. `vagrant up`
4. `vagrant ssh /coord/` # ssh'es to the coordinating node
5. `./update_jenkins_night_rally.sh` # rsyncs night_rally to the jenkins user
6. `sudo -iu jenkins`
7. Run `./test_longrunning.sh`

To iterate on changes, always remember to re-run `./update_jenkins_night_rally.sh` as user `vagrant`, before re-running tests.

##### Iterating on release or nightly benchmarks while testing changes on Rally

If you want to verify your on-going Rally work or a Rally PR against a full nightly or release run, use the following steps: 

1. Specify the Rally repo and branch using the following environment variables:
    ```
    export RALLY_REPO=https://github.com/elastic/rally.git
    export RALLY_BRANCH=master
    ```

    - `RALLY_REPO` can point to any repo e.g. your own fork. Defaults to `https://github.com/elastic/rally.git` if unset.
    - `RALLY_BRANCH` optionally, the branch name. Defaults to `master` if unset.
    - `RALLY_SHA`: optionally, checkout a specific commit from the specified branch. If unset, the latest commit of `RALLY_BRANCH` will be used.
    
2. Choose any of the previous workflows (Iterating on release/nightly benchmarks) and continue with the steps there.

3. If you are working with the `master` branch and don't want Rally to auto-update specify:
    ```
    export SKIP_RALLY_UPDATE=YES
    ```

    before running any of `./test_*.sh`.
    
    More details about the specifics of Rally self-update [here](https://esrally.readthedocs.io/en/stable/developing.html?highlight=skip-update).
    
The Vagrant workflow retrieves credentials to the metrics store via Vault so ensure that it is [properly setup](https://github.com/elastic/infra/blob/master/docs/vault.md#github-auth). By default results will be sent to the Elastic Cloud cluster `night-rally-tests` (details in LastPass). In order to write to a different metrics store, you need to:

1. Add credentials to Vault:

    1.1 Create a file containing the cluster properties, e.g. in `~/cluster-creds.json`:

    ```
    {
    "es_host": "cloud-host-name.eu-central-1.aws.cloud.es.io",
    "es_password": "PASSWORD",
    "es_username": "USERNAME",
    "es_port": "9243",
    "cloud_id": "CLOUD_ID_FROM_UI_AT_CLOUD_ELASTIC_CO",
    "es_secure": "true"
    }
    ```
    1.2 Add the key-value pairs to Vault. Please use `/secret/rally/cloud` as path prefix:

    ```
    vault write /secret/rally/cloud/your-metrics-cluster-name @cluster-creds.json
    ```
    1.3 Check that the data are present

    ```
    vault read /secret/rally/cloud/your-metrics-cluster-name
    ```

    1.4 Delete the cluster properties file

    ```
    rm ~/cluster-creds.json
    ```

2. `export VAULT_NIGHT_RALLY_METRICS_STORE_CREDENTIAL_PATH=/secret/rally/cloud/your-metrics-cluster-name`

Afterwards you can start the Vagrant boxes.

##### Testing fixtures

You can also simulate the application of fixtures like encryption-at-rest.
By default all fixtures are commented out to speed things up (see `/var/lib/jenkins/env_test_script`), but can be overridden by setting an environment variable before running the corresponding test script.
For example setting:

```
export FIXTURES=drop-caches,trim,initialize-data-disk,encryption-at-rest
```

and running `./test_release.sh` will cause all these fixtures to be executed, simulating the expected behavior from the Jenkins job.
