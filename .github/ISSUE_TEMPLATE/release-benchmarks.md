---
name: Run release benchmarks
about: To track progress of benchmarks for a specific Elasticsearch release
title: Run release benchmarks for Elasticsearch x.y.z
labels: benchmark
assignees: ''

---

### Notes

For every task below, after scheduling the job, **set a reminder for yourself at 20:00 UTC** to check the auto-scheduled nightly jobs. If the released job seems to be still running, you should:

1. Cancel the auto-scheduled nightly jobs: use the `x` button after logging in on Jenkins to cancel the pending nightly jobs ([group-1](https://elasticsearch-ci.elastic.co/view/All/job/elastic+elasticsearch+master+macrobenchmark-periodic-group-1/), [group-2](https://elasticsearch-ci.elastic.co/view/All/job/elastic+elasticsearch+master+macrobenchmark-periodic-group-2/)).
2. Re-schedule the nightly jobs using the correct effective start date.

This process is needed to avoid spill over of the start date to the next calendar day. More details in the [night-rally docs](https://github.com/elastic/night-rally/blob/master/42.md#what-time-do-the-nightly-benchmarks-start-what-elasticsearch-commit-do-they-choose).

### Common build parameters

The following parameter needs to be set for every build below:

* `VERSION`: `$VERSION`

### Builds

- [ ] `MODE`: `release`, `RELEASE_LICENSE`: `oss` - triggered by `your user handle here`  as `link to all triggered builds here`
- [ ] `MODE`: `release`, `RELEASE_LICENSE`: `basic` - triggered by `your user handle here`  as `link to all triggered builds here`
- [ ] `MODE`: `release`, `RELEASE_LICENSE`: `trial`, `RELEASE_X_PACK_COMPONENTS`: `security` - triggered by `your user handle here`  as `link to all triggered builds here`
- [ ] `MODE`: `release:docker` (everything else default i.e. `oss`) - triggered by `your user handle here`  as `link to all triggered builds here`
- [ ] `MODE`: `release:encryption-at-rest`, runtime_jdk: `bundled` (everything else default i.e. `oss`) - triggered by `your user handle here`  as `link to all triggered builds here`
