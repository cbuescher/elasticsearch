---
name: JDK Bump
about: Tasks that need to be done to support a new JDK release in benchmarks
title: Add support for JDK xx in Benchmarks
labels: meta
assignees: ''

---

### Rally

* [ ] Create an infra PR to add the new `JAVAx_HOME` in the rally builds (this is needed because Rally builds Elasticsearch from sources)
* [ ] Add the build and runtime JDK in rally-teams - see e.g. https://github.com/elastic/rally-teams/pull/22
* [ ] Expose the new environment variable in Rally in `tox.ini`

### Nightly Benchmarks / Longrunning benchmarks

* [ ] Create an infra PR to add the new JDK for the macrobenchmark machines (nightly, low-mem, longrunning) - see e.g. https://github.com/elastic/infra/pull/9571 (ensure that infra executes Ansible against the machines so the JDK is present there). 
* [ ] Ensure that our Vagrant workflow still works
* [ ] (only if the minimum runtime JDK changes) Create an infra PR to bump the runtime JDK in the build definitions of our nightly macrobenchmark builds
* [ ] (only if the minimum runtime JDK changes) update the runtime JDK in night-rally's config
* [ ] (only if the minimum runtime JDK changes) update the nightly benchmarks index page to mention that we've bumped the runtime JDK.

### Microbenchmarks

* [ ] Create an infra PR to add the new JDK for the microbenchmark machine - see e.g. https://github.com/elastic/infra/pull/16664 (ensure that infra executes Ansible against the machines so the JDK is present there). 
* [ ] Create an infra PR to bump the JDK in microbenchmark builds: e.g. https://github.com/elastic/infra/pull/16663
