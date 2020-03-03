**New here? Please check our [benchmark one stop page](42.md) which should answer most of your questions.**

## Night Rally

Night Rally is a set of driver scripts for [running nightly macrobenchmarks for Elasticsearch](https://elasticsearch-ci.elastic.co/view/All/job/elastic+elasticsearch+master+macrobenchmark-periodic) and [publishing the results](https://elasticsearch-benchmarks.elastic.co/). The macrobenchmarks themselves are executed by [Rally](https://github.com/elastic/rally).

### Prerequisites

* `awscli` available on the command line and properly set up to write to the bucket `s3://elasticsearch-benchmarks.elasticsearch.org`.
* All prerequisites for [Rally](https://github.com/elastic/rally)

Night Rally is only tested on Mac OS X and Linux.

### Getting Started

1. Ensure that all prerequisites of [Rally](https://github.com/elastic/rally) are properly setup. Hint: It is *not* required to install Rally manually. Just ensure that its prerequisites are installed.
2. Clone this repo: `git clone git@github.com:elastic/night-rally.git`
3. [Setup Vault](https://github.com/elastic/infra/blob/master/docs/vault.md)
4. Run `make setup`

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

* Add an annotation for all charts for a specific nightly benchmark trial: `night-rally-admin add annotation --environment=nightly --race-timestamp=20170502T220213Z --message="Just a test annotation"`
* Add an annotation for all charts of one track for a specific nightly benchmark trial: `night-rally-admin add annotation --environment=nightly --race-timestamp=20170502T220213Z --track=geonames --message="Just a test annotation for geonames"`
* Add an annotation for a specific chart of one track for a specific nightly benchmark trial: `night-rally-admin add annotation --environment=nightly --race-timestamp=20170502T220213Z --track=geonames --chart=io --message="Just a test annotation"`

For more details, please issue `night-rally-admin add annotation --help`.

**Note:** The admin tool also supports a dry-run mode for all commands that would change the data store. Just append `--dry-run`.

**Note:** The new annotation will show up immediately.

#### Remove an annotation

If you have made an error you can also remove specific annotations by id.

1. Issue `night-rally-admin list annotations --environment=nightly` and find the right annotation. Note that only the 20 most recent annotations are shown. You can show more, by specifying `--limit=NUMBER`.
2. Suppose the id of the annotation that we want to delete is `AVwM0jAA-dI09MVLDV39`. Then issue `night-rally-admin delete annotation --id=AVwM0jAA-dI09MVLDV39`.

For more details, please issue `night-rally-admin delete annotation --help`.

#### Remove a race

Sometimes we need to redo a benchmark run and then we need to cleanup data from the prior run. In order to do so, `night-rally-admin` can delete all relevant data.

1. Issue `night-rally-admin list races --environment=nightly` and find the race id of the race(s) you need to delete. Note that only the 20 most recent races are shown. You can show more, by specifying `--limit=NUMBER`.
2. Suppose the id of the race that we want to delete is `53f37522-b761-4e46-9a5c-e7f0d9d9258f`. Then issue `night-rally-admin delete race --id=53f37522-b761-4e46-9a5c-e7f0d9d9258f`. This will remove all data about this race from the metrics store.

For more details, please issue `night-rally-admin delete race --help`.

**Note:** The admin tool also supports a dry-run mode for all commands that would change the data store. Just append `--dry-run`.

#### Find logs, telemetry or heapdumps from older nightly runs

Each nightly execution wipes the data disk on target machines (`~/.var/lib/jenkins/rally/benchmarks/races`) as part of the initial [setup fixture](https://github.com/elastic/night-rally/tree/master/night_rally/fixtures/ansible/roles/initialize-data-disk).
Important information from earlier nightly executions, specifically the `heapdump`, `logs` and `telemetry` subdirectories from each race id are copied under `/var/lib/jenkins/race_archive/<YYYYMMDD>` on each target machine, for future reference.
This is done as the last step before the nightly run has finished. 

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

#### Retrigger a failed nightly benchmark

Rally allows to benchmark arbitrary (recent) commits in Elasticsearch. Night-Rally uses the concept of an "effective start date" to determine:
 
* Which commit should be benchmarked by Rally.
* Which race timestamp to use for the nightly charts.

Therefore, we need to ensure we set the corresponding build parameter `EFFECTIVE_START_DATE` in the nightly CI builds. Suppose a benchmark has failed that has originally been run with the effective start date "20200220T180634Z" (look for e.g. `18:13:14 [2020-02-20 18:13:14][INFO] Effective start date is [2020-02-20 18:06:34]` in the Jenkins console ouput).

1. Ensure that [all machines in the affected benchmark environment](42.md#where-are-the-benchmark-machines) are in a clean state (no hanging processes etc.) by logging in to each machine as user `jenkins` (`sudo -iu jenkins`). Then check (and terminate if needed):
    1. Any leftover Elasticsearch processes: `ps -ef | grep -i java | grep -v swarm-client`. Note that on the load driver machines one Java process, the Jenkins swarm client, is running (and should keep running) so please make sure you don't terminate it accidentally. 
    2. Any leftover Rally processes: `ps -ef | grep -i rally`

2. Use `night-rally-admin` to determine the race ids of the failed races:

```
night-rally-admin list races --environment=nightly
```

The output might look as follows (by default, the 20 most recent races are shown; use `--limit=N` to increase the limit or `--from-date=yyyyMMdd` / `--to-date=yyyyMMdd` to show only the relevant date range):

```
Race Timestamp    Race Id                               Track       Challenge                               Car                                               Version         Revision                                  Track Revision    Team Revision    User Tags
----------------  ------------------------------------  ----------  --------------------------------------  ------------------------------------------------  --------------  ----------------------------------------  ----------------  ---------------  --------------------------------------------------------------------------------------------------------------------------
20200220T180634Z  0afb2330-ba14-43f0-87d8-6c9d45aba057  geonames    append-fast-with-conflicts              ['4gheap']                                        8.0.0-SNAPSHOT  dc070a541e5ef343bca11fb08715b8b2ba0c2e16  84281be           cb01613          license=oss, name=geonames-update-4g-1node, race-configs-id=race-configs-group-1.json, setup=bare-oss
20200220T180634Z  818c8460-00e8-4652-acc8-2adfd74490fb  geonames    append-no-conflicts                     ['defaults', 'basic-license']                     8.0.0-SNAPSHOT  dc070a541e5ef343bca11fb08715b8b2ba0c2e16  84281be           cb01613          license=basic, name=geonames-append-defaults-1node, race-configs-id=race-configs-group-1.json, setup=bare-oss
20200220T180634Z  ce509f1a-97ed-43ea-80a9-d35fc8573f5c  geonames    append-no-conflicts                     ['defaults']                                      8.0.0-SNAPSHOT  dc070a541e5ef343bca11fb08715b8b2ba0c2e16  84281be           cb01613          license=oss, name=geonames-append-defaults-1node, race-configs-id=race-configs-group-1.json, setup=bare-oss
20200220T180634Z  cacdfca0-5d46-4710-9cb1-ae9f9c857b07  geonames    append-no-conflicts-index-only          ['4gheap']                                        8.0.0-SNAPSHOT  dc070a541e5ef343bca11fb08715b8b2ba0c2e16  84281be           cb01613          license=oss, name=geonames-append-4g-3nodes, race-configs-id=race-configs-group-1.json, setup=bare-oss
20200220T180634Z  4915ad96-a45d-4ccb-af3b-cb4dc28bd7c2  geonames    append-no-conflicts-index-only          ['4gheap']                                        8.0.0-SNAPSHOT  dc070a541e5ef343bca11fb08715b8b2ba0c2e16  84281be           cb01613          license=oss, name=geonames-append-4g-1node, race-configs-id=race-configs-group-1.json, setup=bare-oss
20200220T180634Z  b46314e6-98eb-46e8-a30f-91e75e65e7fc  geonames    append-no-conflicts-index-only          ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  dc070a541e5ef343bca11fb08715b8b2ba0c2e16  84281be           cb01613          license=basic, name=geonames-append-4g-3nodes, race-configs-id=race-configs-group-1.json, setup=bare-oss
20200220T180634Z  7de0c6d5-cda6-4706-8eb6-890ea7e4a5b4  geonames    append-sorted-no-conflicts              ['4gheap']                                        8.0.0-SNAPSHOT  dc070a541e5ef343bca11fb08715b8b2ba0c2e16  84281be           cb01613          license=oss, name=geonames-appendsorted-4g-1node, race-configs-id=race-configs-group-1.json, setup=bare-oss
20200220T180634Z  34b6e37e-67e8-4b65-928a-d498fe7360de  nested      nested-search-challenge                 ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  dc070a541e5ef343bca11fb08715b8b2ba0c2e16  84281be           cb01613          license=basic, name=nested-append-4g-1node, race-configs-id=race-configs-group-2.json, setup=bare-oss
20200220T180634Z  eb2103fb-6621-4fba-acff-e3048c40ccd6  nested      nested-search-challenge                 ['4gheap']                                        8.0.0-SNAPSHOT  dc070a541e5ef343bca11fb08715b8b2ba0c2e16  84281be           cb01613          license=oss, name=nested-append-4g-1node, race-configs-id=race-configs-group-2.json, setup=bare-oss
20200220T180634Z  b07deca5-5d8e-41bb-96ee-fb9a3908ceb5  noaa        append-no-conflicts                     ['defaults', 'basic-license']                     8.0.0-SNAPSHOT  dc070a541e5ef343bca11fb08715b8b2ba0c2e16  84281be           cb01613          license=basic, name=noaa-append-defaults-1node, race-configs-id=race-configs-group-2.json, setup=bare-oss
20200220T180634Z  d8bc7218-e371-473b-bd14-df88fdea8cff  noaa        append-no-conflicts                     ['defaults']                                      8.0.0-SNAPSHOT  dc070a541e5ef343bca11fb08715b8b2ba0c2e16  84281be           cb01613          license=oss, name=noaa-append-defaults-1node, race-configs-id=race-configs-group-2.json, setup=bare-oss
20200220T180634Z  c4af1ac2-540e-4382-9c27-d12f9f46aed9  pmc         append-no-conflicts                     ['4gheap']                                        8.0.0-SNAPSHOT  dc070a541e5ef343bca11fb08715b8b2ba0c2e16  84281be           cb01613          license=oss, name=pmc-append-4g-3nodes, race-configs-id=race-configs-group-2.json, setup=bare-oss
20200219T215555Z  f8210d48-d169-4adb-87fb-5a45768bd8c3  http_logs   append-index-only-with-ingest-pipeline  ['4gheap']                                        8.0.0-SNAPSHOT  e057f65a7d17c7daea530ba3e451063e31584bc4  84281be           cb01613          license=oss, name=http_logs-grok-no-src-1node, race-configs-id=race-configs-group-2.json, setup=bare-oss
20200219T215555Z  a0afbd05-ebfd-4cc3-b246-08253412bc21  http_logs   append-index-only-with-ingest-pipeline  ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  e057f65a7d17c7daea530ba3e451063e31584bc4  84281be           cb01613          license=basic, name=http_logs-grok-no-src-1node, race-configs-id=race-configs-group-2.json, setup=bare-oss
20200219T215555Z  aeff2a81-741e-4085-8cdc-fd1a7f4b2c07  http_logs   append-no-conflicts                     ['4gheap', 'g1gc']                                8.0.0-SNAPSHOT  e057f65a7d17c7daea530ba3e451063e31584bc4  84281be           cb01613          license=oss, name=http_logs-append-4g-g1gc-1node, race-configs-id=race-configs-group-2.json, setup=bare-oss
20200219T215555Z  70a8ab49-c0f5-463a-a911-9522d7612eaa  http_logs   append-no-conflicts                     ['4gheap']                                        8.0.0-SNAPSHOT  e057f65a7d17c7daea530ba3e451063e31584bc4  84281be           cb01613          license=oss, name=http_logs-append-4g-1node, race-configs-id=race-configs-group-2.json, setup=bare-oss
...
``` 

3. Grab the race ids from the affected timestamp and delete the results of all affected race ids:

You can append `--dry-run` to test it first (in this example we show only one id for brevity): 

```
night-rally-admin delete race --environment=nightly --id="0afb2330-ba14-43f0-87d8-6c9d45aba057" --dry-run
```

after you've verified that the command is fine, remove `--dry-run` to actually delete the affected data: 

```
night-rally-admin delete race --environment=nightly --id="0afb2330-ba14-43f0-87d8-6c9d45aba057,818c8460-00e8-4652-acc8-2adfd74490fb,ce509f1a-97ed-43ea-80a9-d35fc8573f5c,cacdfca0-5d46-4710-9cb1-ae9f9c857b07,4915ad96-a45d-4ccb-af3b-cb4dc28bd7c2,b46314e6-98eb-46e8-a30f-91e75e65e7fc,7de0c6d5-cda6-4706-8eb6-890ea7e4a5b4,34b6e37e-67e8-4b65-928a-d498fe7360de,eb2103fb-6621-4fba-acff-e3048c40ccd6,b07deca5-5d8e-41bb-96ee-fb9a3908ceb5,d8bc7218-e371-473b-bd14-df88fdea8cff,c4af1ac2-540e-4382-9c27-d12f9f46aed9,f8210d48-d169-4adb-87fb-5a45768bd8c3,a0afbd05-ebfd-4cc3-b246-08253412bc21,aeff2a81-741e-4085-8cdc-fd1a7f4b2c07,70a8ab49-c0f5-463a-a911-9522d7612eaa"
```

4. Verify that the data points are gone (reissuing the command from step 2)

5. Retrigger a build via Jenkins. Be sure to set `EFFECTIVE_START_DATE` to the same timestamp (i.e. `2020-02-20 18:06:34` in our example) when triggering the build. This is crucial to ensure that the correct commit is benchmarked!

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
