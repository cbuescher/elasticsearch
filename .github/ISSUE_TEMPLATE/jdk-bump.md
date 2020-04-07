---
name: JDK Bump
about: Tasks that need to be done to support a new JDK release in benchmarks
title: Add support for JDK $VERSION in Benchmarks
labels: meta
assignees: ''

---

JDK $VERSION should be release on date ([source](https://openjdk.java.net/projects/jdk/$VERSION/)) and we should update our benchmark machines accordingly soon after that date.

### Rally

* [ ] Create an infra PR to add the new `JAVA$VERSION_HOME` in the rally builds (this is needed because Rally builds Elasticsearch from sources) - e.g. https://github.com/elastic/infra/pull/19281
* [ ] Add the build and runtime JDK in rally-teams - e.g. https://github.com/elastic/rally-teams/pull/48
* [ ] Expose the new environment variable in Rally in `tox.ini` - e.g. https://github.com/elastic/rally/pull/953

### Nightly Benchmarks / Longrunning benchmarks

* [ ] Create an infra PR to add the new JDK for the macrobenchmark machines (nightly, low-mem, longrunning) - e.g. https://github.com/elastic/infra/pull/19281 (ensure that infra executes the Ansible commands below against the machines so the JDK is present there). 
* [ ] Expose `JAVA$VERSION_HOME` when starting the Rally daemon via night-rally - e.g. https://github.com/elastic/night-rally/pull/235
* [ ] Ensure that our Vagrant workflow still works - e.g. https://github.com/elastic/night-rally/pull/234

### Microbenchmarks

* [x] Create an infra PR to add the new JDK for the microbenchmark machine - e.g. https://github.com/elastic/infra/pull/19281 (ensure that infra executes the Ansible commands below against the machines so the JDK is present there). 
* [x] Create an infra PR to bump the JDK in microbenchmark builds - e.g. https://github.com/elastic/infra/pull/19281

### Ansible

To install the new Java version on all environments, run the following commands after the respective infra PR(s) has been merged from the `ansible` directory in the infra repository:

```
ansible-playbook -u $SSH_USER -i inventory/production playbooks/longrunbenchmarks.yml --limit longrunbenchmarks --tags java

ansible-playbook -u $SSH_USER -i inventory/production playbooks/macrobenchmarks_targets.yml --limit macrobenchmarks-targets --tags java

ansible-playbook -u $SSH_USER -i inventory/production playbooks/macrobenchmarks_targets.yml --limit memorybenchmarks --tags java

ansible-playbook -u $SSH_USER -i inventory/production playbooks/macrobenchmarks_targets.yml --limit macrobenchmarks-targets-group-1 --tags java

ansible-playbook -u $SSH_USER -i inventory/production playbooks/macrobenchmarks_targets.yml --limit macrobenchmarks-targets-group-2 --tags java

ansible-playbook -u $SSH_USER -i inventory/production playbooks/jenkins_workers.yml --limit elasticsearch-ci-workers-microbenchmarks --tags java
```

`$SSH_USER` is your remote user name on the bare metal machines.
