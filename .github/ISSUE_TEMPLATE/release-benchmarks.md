---
name: Run release benchmarks
about: To track progress of benchmarks for a specific Elasticsearch release
title: Run release benchmarks for Elasticsearch x.y.z
labels: benchmark
assignees: ''

---

IMPORTANT NOTE
-------------------
For every task below, after scheduling the job, remember to cancel nightly jobs on [group-1](https://elasticsearch-ci.elastic.co/view/All/job/elastic+elasticsearch+master+macrobenchmark-periodic-group-1/) and [group-2](https://elasticsearch-ci.elastic.co/view/All/job/elastic+elasticsearch+master+macrobenchmark-periodic-group-2/) that get autoscheduled at 20:00 UTC.
If your released job seems to be still running, cancel them (use the x button after logging in on Jenkins) and reschedule using the correct effective start date.
More details in [night-rally docs](https://github.com/elastic/night-rally/blob/master/42.md#what-time-do-the-nightly-benchmarks-start-what-elasticsearch-commit-do-they-choose).

- [ ] mode: `release`, release_license: `oss` - triggered by `your user handle here`  as `link to all triggered builds here`
- [ ] mode: `release`, release_license: `basic` - triggered by `your user handle here`  as `link to all triggered builds here`
- [ ] mode: `release`, RELEASE_LICENSE: `trial` + RELEASE_X_PACK_COMPONENTS: `security` - triggered by `your user handle here`  as `link to all triggered builds here`
- [ ] mode: `release:docker` (everything else default i.e. `oss`) - triggered by `your user handle here`  as `link to all triggered builds here`
- [ ] mode: `release:encryption-at-rest` (everything else default i.e. `oss`) - triggered by `your user handle here`  as `link to all triggered builds here`
