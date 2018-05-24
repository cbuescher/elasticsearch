Contains the necessary Ansible scripts to:

* Update Rally on any affected machines before executing a benchmark (playbook `update-rally`)
* Run fixtures against all benchmark target machines (playbook `setup`)

It also defines a Vagrant box to test the playbooks locally. In order to this, startup the box:
 
```
vagrant up ubuntu-16.04.benchmarks.ci.vagrant
```
 
To setup an encrypted volume on `/dev/sdb` on all target machines, run:
 
```
ansible-playbook playbooks/setup.yml
```

To setup an unencrypted volume on `/dev/sdb` on all target machines, run:

```
ansible-playbook playbooks/setup.yml --skip-tags encryption-at-rest
```

The scripts work in any order.