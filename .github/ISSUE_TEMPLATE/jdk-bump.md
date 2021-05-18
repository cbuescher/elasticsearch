---
name: JDK Bump
about: Tasks that need to be done to support a new JDK release in benchmarks
title: Add support for JDK $VERSION in Benchmarks
labels: meta
assignees: ''

---

JDK $VERSION should be release on date ([source](https://openjdk.java.net/projects/jdk/$VERSION/)) and we should update our benchmark machines accordingly soon after that date.

### Rally

* [ ] Check if new definitions are needed for `java_custom_versions:` in [defaults.yml](https://github.com/elastic/infra/blob/16dabef9ff2f628b6c77329414952cf015a5d614/ansible/roles/java/defaults/main.yml#L7-L65) of infra's `java` role; if they are missing, add them with a PR like [infra#29041](https://github.com/elastic/infra/pull/29041)
* [ ] Execute yourself, or ensure that infra executes the following Ansible command:

    ```
    ansible-playbook -u $SSH_USER -i inventory/production playbooks/macrobenchmarks_targets.yml --limit macrobenchmarks-targets-all --tags java
    ```
   `$SSH_USER` is your remote user name on the bare metal machines.`

* [ ] Add the build and runtime JDK in rally-teams - e.g. https://github.com/elastic/rally-teams/pull/48
* [ ] Expose the new environment variable in Rally in `tox.ini` - e.g. https://github.com/elastic/rally/pull/953

### Nightly Benchmarks

* [ ] Expose `JAVA$VERSION_HOME` when starting the Rally daemon via night-rally - e.g. https://github.com/elastic/night-rally/pull/235
* [ ] Ensure that our Vagrant workflow still works - e.g. https://github.com/elastic/night-rally/pull/234
