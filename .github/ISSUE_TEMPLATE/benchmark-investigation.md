---
name: Benchmark investigation
about: Template for Elasticsearch benchmark investigations
title: Investigate delta in xx track
labels: investigation
assignees: ''

---

In the nightly benchmarks for [date] [statement defining what the issue is]. Include relevant images from https://elasticsearch-benchmarks.elastic.co/index.html

#### Races
The race ids in question as determined by `night-rally-admin list races --environment=...`

```
Include a table of races of interest
```

#### Commits
The [list of changes in Elasticsearch between the two nightly runs](https://github.com/elastic/elasticsearch/compare/BASELINE_SHA_HERE...REGRESSED_SHA_HERE).

#### Comparison of metrics

Include commands run (ex: `esrally compare --configuration-name=nightly ..`) and relevant rows of data to enforce the issue.

#### Reproduction

Include any relevant rally runs here that might prove a particular commit confirms the issue.
