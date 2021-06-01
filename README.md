**New here? Please check our [benchmark one stop page](42.md) which should answer most of your questions.**

## Night Rally

Night Rally is a set of driver scripts for running nightly macrobenchmarks for Elasticsearch and [publishing the results](https://elasticsearch-benchmarks.elastic.co/). The macrobenchmarks themselves are executed by [Rally](https://github.com/elastic/rally).

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

Find the relevant revision One possibility is to run e.g. `night-rally-admin list races --environment=nightly --track=geonames --license=trial --from-date=20201207` which provides the following list:

```
Race Timestamp    Race Id                               Track     Challenge            Car                                               ES Version      Revision                                  Rally Version                       Track Revision    Team Revision    User Tags
----------------  ------------------------------------  --------  -------------------  ------------------------------------------------  --------------  ----------------------------------------  ----------------------------------  ----------------  ---------------  ----------------------------------------------------------------------------------------------------------------------------
20201208T200053Z  e83e9161-ed9c-44ee-8f29-17260e820bf3  geonames  append-no-conflicts  ['defaults', 'trial-license', 'x-pack-security']  8.0.0-SNAPSHOT  c76058d0b3ca1e14ce4126ff6eb2a68b741b90f0  2.0.3.dev0 (git revision: b143899)  47b7054           3d59034          license=trial, name=geonames-append-defaults-1node, race-configs-id=race-configs-group-1.json, setup=bare-basic, x-pack=true
20201207T200113Z  f133d0f0-7d24-49d3-ab08-35209d6c2c5e  geonames  append-no-conflicts  ['defaults', 'trial-license', 'x-pack-security']  8.0.0-SNAPSHOT  5859c4d6e62606428c2e49a181c7f845cadabecb  2.0.3.dev0 (git revision: b143899)  47b7054           3d59034          license=trial, name=geonames-append-defaults-1node, race-configs-id=race-configs-group-1.json, setup=bare-basic, x-pack=true
```

You can see the revisions `5859c4d6e62606428c2e49a181c7f845cadabecb` and `c76058d0b3ca1e14ce4126ff6eb2a68b741b90f0`. If you want to see which commits are included in between, open the Github compare view with https://github.com/elastic/elasticsearch/compare/5859c4d6e62606428c2e49a181c7f845cadabecb...c76058d0b3ca1e14ce4126ff6eb2a68b741b90f0.


#### Add an annotation

To add an annotation, use the admin tool. First find the correct race timestamp by issuing `night-rally-admin list races --environment=nightly`. You will need the race timestamp later. Below are examples for common cases:

* Add an annotation for all charts for a specific nightly benchmark race: `night-rally-admin add annotation --environment=nightly --race-timestamp=20170502T220213Z --message="Just a test annotation"`
* Add an annotation for all charts of one track for a specific nightly benchmark race: `night-rally-admin add annotation --environment=nightly --race-timestamp=20170502T220213Z --track=geonames --message="Just a test annotation for geonames"`
* Add an annotation for a specific chart type of one track for a specific nightly benchmark race: `night-rally-admin add annotation --environment=nightly --race-timestamp=20170502T220213Z --track=geonames --chart-type=io --message="Just a test annotation"`
* Add an annotation for a specific chart name for a specific nightly benchmark race: `night-rally-admin add annotation --environment=nightly --race-timestamp=20170502T220213Z --chart-name=nightly-basic-geonames-add-defaults-country_agg_uncached-latency --message="Just a test annotation"`

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

Benchmarks get executed in three environments, group-1 / group-2 / group-3 (see [infra repo](https://github.com/elastic/infra/blob/master/ansible/inventory/production/hetzner/benchmarks)).

The following steps are necessary to add a new track:

1. Add your track and the challenges to run in `resources/race-configs-group-?.json`.
2. Generate nightly charts and the corresponding dashboards with Rally: `esrally generate charts --configuration-name=nightly --chart-spec-path=$NIGHT_RALLY_HOME/night_rally/resources/race-configs-group-?.json --chart-type=time-series --output-path=nightly-charts.ndjson`
3. Generate release charts and the corresponding dashboard with Rally: `esrally generate charts --configuration-name=release --chart-spec-path=$NIGHT_RALLY_HOME/night_rally/resources/race-configs-group-?.json --chart-type=bar --output-path=release-charts.ndjson`
4. Import the new charts to the corresponding dashboards on the [Kibana instance](https://ae582947d1ed4df0adc39c2d047e051a.eu-central-1.aws.cloud.es.io) (it's mapped to be publicly reachable). Please import only the charts for the new track and skip any existing ones.
5. Add the name of your track and the UUIDs of the dashboards that you've created in step two and three to the array at the bottom of `external/pages/index.html`.

If you're finished, please submit a PR. After the PR is merged, we will deploy the new page using the script in `external/pages/deploy.sh` and the dashboards for the new track will show up immediately.

#### Run a release benchmark

Raise a [release benchmark issue](https://github.com/elastic/night-rally/issues/new?assignees=&labels=benchmark&template=release-benchmarks.md&title=Run+release+benchmarks+for+Elasticsearch+x.y.z) and follow the steps outlined in the template.

#### Retrigger a failed nightly benchmark

Rally allows to benchmark arbitrary (recent) commits in Elasticsearch. Night-Rally uses the concept of an "effective start date" to determine:

* Which commit should be benchmarked by Rally.
* Which race timestamp to use for the nightly charts.

Therefore, we need to ensure we set the corresponding build parameter `EFFECTIVE_START_DATE` in the nightly CI builds. Suppose a benchmark has failed that has originally been run with the effective start date "20200220T180634Z" (look for e.g. `18:13:14 [2020-02-20 18:13:14][INFO] Effective start date is [2020-02-20 18:06:34]` in the Jenkins console ouput).

1. Ensure that [all machines in the affected benchmark environment](https://wiki.elastic.co/pages/viewpage.action?pageId=135076508) are in a clean state (no hanging processes etc.) by logging in to each machine as user `jenkins` (`sudo -iu jenkins`). Then check (and terminate if needed):
    1. Any leftover Elasticsearch processes: `ps -ef | grep -i java | grep -v swarm-client`. Note that on the load driver machines one Java process, the Jenkins swarm client, is running (and should keep running) so please make sure you don't terminate it accidentally.
    2. Any leftover Rally processes: `ps -ef | grep -i rally`

2. Use `night-rally-admin` to determine the race ids of the failed races:

```
night-rally-admin list races --environment=nightly
```

The output might look as follows (by default, the 20 most recent races are shown; use `--limit=N` to increase the limit or `--from-date=yyyyMMdd` / `--to-date=yyyyMMdd` to show only the relevant date range):

```
Race Timestamp    Race Id                               Track      Challenge                               Car                                               ES Version      Revision                                  Rally Version                       Track Revision    Team Revision    User Tags
----------------  ------------------------------------  ---------  --------------------------------------  ------------------------------------------------  --------------  ----------------------------------------  ----------------------------------  ----------------  ---------------  --------------------------------------------------------------------------------------------------------------------------
20201021T200101Z  db185340-2cf4-4537-890c-5a9a5c910f2a  http_logs  append-index-only-with-ingest-pipeline  ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=http_logs-grok-no-src-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  51e082ad-09a0-4a89-a26c-ceabada76ce3  http_logs  append-no-conflicts                     ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=http_logs-append-4g-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  f83df115-7c0c-4146-948b-84675ff3f86c  http_logs  append-no-conflicts                     ['4gheap', 'trial-license', 'x-pack-security']    8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=trial, name=http_logs-append-4g-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic, x-pack=true
20201021T200101Z  816e9084-da7c-4f59-9767-18a9b7a4cdb5  http_logs  append-no-conflicts-index-only          ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=http_logs-append-4g-3nodes, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  365497eb-179a-461b-bc66-24926eb19505  http_logs  append-no-conflicts-index-only          ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=http_logs-no-src-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  410351b5-e5c3-4bfc-92b2-cdf1de6bbd40  http_logs  append-no-conflicts-index-only          ['defaults', 'basic-license']                     8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=http_logs-append-defaults-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  552482e7-7bf9-4c18-863a-22c12eeeb930  http_logs  append-sorted-no-conflicts              ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=http_logs-appendsorted-4g-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  991b63ee-1ca7-4e1b-82eb-c23c820c3031  nested     nested-search-challenge                 ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=nested-append-4g-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  36169d6a-6f6f-4b2d-9cf9-fa4e67966d9f  noaa       append-no-conflicts                     ['defaults', 'basic-license']                     8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=noaa-append-defaults-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  c691f0b0-d8b7-41f8-88a1-fe5b2e38a95e  pmc        append-fast-with-conflicts              ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=pmc-update-4g-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  0df6672c-4395-4a23-8d9b-a16c54f2038c  pmc        append-no-conflicts                     ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=pmc-append-4g-3nodes, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  3a0d236e-8f96-41fa-b2db-054cfa98f625  pmc        append-no-conflicts                     ['4gheap', 'unpooled', 'basic-license']           8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=pmc-nio-4g-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  b5993d4f-d846-403c-a68f-8956926f27af  pmc        append-no-conflicts                     ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=pmc-append-4g-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  b85f6110-74ff-4493-95f8-83a4b644ce10  pmc        append-no-conflicts                     ['4gheap', 'trial-license', 'x-pack-security']    8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=trial, name=pmc-append-4g-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic, x-pack=true
20201021T200101Z  9dc3cd20-c0e2-4791-810f-d98f8167a2e4  pmc        append-no-conflicts-index-only          ['4gheap', 'unpooled', 'basic-license']           8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=pmc-nio-4g-3nodes, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  16bcff40-18d5-4232-a85e-b2bc8c4d1501  pmc        append-no-conflicts-index-only          ['defaults', 'basic-license']                     8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=pmc-append-defaults-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200101Z  c94893fb-ad30-43ea-bfa7-abe6fe9aa40c  pmc        append-sorted-no-conflicts              ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=pmc-appendsorted-4g-1node, race-configs-id=race-configs-group-2.json, setup=bare-basic
20201021T200056Z  a7d1ce87-b3ca-4d8b-b1a8-341f030bce14  geonames   append-fast-with-conflicts              ['4gheap', 'basic-license']                       8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=geonames-update-4g-1node, race-configs-id=race-configs-group-1.json, setup=bare-basic
20201021T200056Z  e87c3acb-411c-4b70-be0e-07e6027f7188  geonames   append-no-conflicts                     ['defaults', 'basic-license']                     8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=basic, name=geonames-append-defaults-1node, race-configs-id=race-configs-group-1.json, setup=bare-basic
20201021T200056Z  96855d62-fd69-4947-b35c-d75f4c00c546  geonames   append-no-conflicts                     ['defaults', 'trial-license', 'x-pack-security']  8.0.0-SNAPSHOT  165e063b500fabb7eeeb29a42f8d42b09de7611b  2.0.2.dev0 (git revision: 8836cd6)  251215f           c50cf90          license=trial, name=geonames-append-defaults-1node, race-configs-id=race-configs-group-1.json, setup=bare-basic, x-pack=true
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

## Common issues with the bare metal environments (Hetzner)

See our list of the [current bare metal environments](https://wiki.elastic.co/pages/viewpage.action?pageId=135076508).

### Replacing a faulty disk

See the runbook [how to have a faulty disk replaced](https://wiki.elastic.co/display/DEV/Drive+Failure).

### Swapping network public/private NIC device names after re-bootstrapping the OS

Occasionally there is a need to ask Infra to reinstall the operating system (e.g. due to failed disks).
Due to random conditions in Hetzner's OS installation scripts this may result in `eth0` / `eth1` NIC device names to get
swapped. Normally `eth0` is the public IP address, which has strict firewall rules, whereas `eth1` points to the 10Gbps
internal interconnect NIC which is whitelisted in firewall rules (example rules in the [infra repo](https://github.com/elastic/infra/blob/master/ansible/playbooks/group_vars/elasticsearch-ci-workers-macrobenchmarks-group-1/firewall.yml#L8)).

This situation is resolvable following the steps shown below; the example assumes that currently `eth1` is the NIC using
the public IP and `eth0` the internal interconnect NIC and we want to swap them:

_Step 1: Become root on the server_

``` shell
dliappis@target-669380:~$ sudo su -
```

_Step 2: Assign the right IP to the right NIC_
```shell
# Show IP definitions per interface
root@target-669380 ~ # cat /etc/network/interfaces
### Hetzner Online GmbH installimage

source /etc/network/interfaces.d/*

auto lo
iface lo inet loopback
iface lo inet6 loopback

auto eth1
iface eth1 inet static
  address 94.130.140.197
  netmask 255.255.255.192
  gateway 94.130.140.193
  # route 94.130.140.192/26 via 94.130.140.193
  up route add -net 94.130.140.192 netmask 255.255.255.192 gw 94.130.140.193 dev eth1

# Switch to use `eth0` for public IP
root@target-669380 ~ # sed -i 's/eth1/eth0/g' /etc/network/interfaces

# Verify changes
root@target-669380 ~ # cat /etc/network/interfaces
### Hetzner Online GmbH installimage

source /etc/network/interfaces.d/*

auto lo
iface lo inet loopback
iface lo inet6 loopback

auto eth0
iface eth0 inet static
  address 94.130.140.197
  netmask 255.255.255.192
  gateway 94.130.140.193
  # route 94.130.140.192/26 via 94.130.140.193
  up route add -net 94.130.140.192 netmask 255.255.255.192 gw 94.130.140.193 dev eth0

# Check the internal NIC:
root@target-669380 ~ # cat /etc/network/interfaces.d/eth1
auto eth0
iface eth0 inet static
address 192.168.14.80
netmask 255.255.255.0

# Use the right name for the internal NIC
root@target-669380 ~ # mv /etc/network/interfaces.d/eth0 /etc/network/interfaces.d/eth1

# Ensure eth1 gets the private IP address
root@target-669380 ~ # sed -i 's/eth0/eth1/g' /etc/network/interfaces.d/eth1

# Verify that the internal NIC is eth1 and has the correct private IP
root@target-669380 ~ # cat /etc/network/interfaces.d/eth1
auto eth1
iface eth1 inet static
address 192.168.14.80
netmask 255.255.255.0
```

_Step 3: Fix the NIC persistent mappings_
``` shell
# Check current NIC mapping
root@target-669380 ~ # cat /etc/udev/rules.d/70-persistent-net.rules
### Hetzner Online GmbH installimage

SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", ATTR{address}=="00:1b:21:db:91:ea", ATTR{dev_id}=="0x0", ATTR{type}=="1", KERNEL=="eth*", NAME="eth0"
SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", ATTR{address}=="90:1b:0e:de:dd:a6", ATTR{dev_id}=="0x0", ATTR{type}=="1", KERNEL=="eth*", NAME="eth1"

# Edit the file and swap `eth0` <--> `eth1`
root@target-669380 ~ # vi /etc/udev/rules.d/70-persistent-net.rules

# Should now look like (note the difference with the MAC address from the previous cat command):
root@target-669380 ~ # cat /etc/udev/rules.d/70-persistent-net.rules
### Hetzner Online GmbH installimage

SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", ATTR{address}=="90:1b:0e:de:dd:a6", ATTR{dev_id}=="0x0", ATTR{type}=="1", KERNEL=="eth*", NAME="eth0"
SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", ATTR{address}=="00:1b:21:db:91:ea", ATTR{dev_id}=="0x0", ATTR{type}=="1", KERNEL=="eth*", NAME="eth1"
```

_Step 4: Fix the firewall rules_
```
# Check whether current firewall rules assume that eth0 is the private NIC
root@target-669380 ~ # grep eth0 /etc/firewall.bash
iptables -A INPUT -p all -i eth0 -j ACCEPT

# Swap eth0 to eth1 in firewall rules
root@target-669380 ~ # sed -i 's/eth0/eth1/g' /etc/firewall.bash
```

_Step 5: Reboot_

``` shell
# reboot
```
