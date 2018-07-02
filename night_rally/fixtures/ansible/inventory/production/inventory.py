#!/usr/bin/env python

'''
Extremely simple dynamic inventory script for Ansible.

Expects TARGET_HOSTS env var to create the target-hosts group
and COORDINATING_NODES env var to create the coordinating-nodes group.
'''

import argparse
import os

try:
    import json
except ImportError:
    import simplejson as json

ANSIBLE_SSH_PRIVATE_KEY_FILE = "/var/lib/jenkins/.ssh/rally"
ANSIBLE_USER = "rally"

class Inventory(object):
    def __init__(self):
        self.inventory = {}
        self.read_cli_args()

        # Called with `--list`
        if self.args.list:
            self.inventory = self.build_inventory()
        # Called with `--host [hostname]`
        elif self.args.host:
            # Not implemented as `--list`` returns _meta
            # see https://docs.ansible.com/ansible/latest/dev_guide/developing_inventory.html#tuning-the-external-inventory-script
            self.inventory = self.empty_inventory()
        # --refresh is a no-op as we don't cache results
        elif self.args.refresh:
            return
        else:
            self.inventory = self.empty_inventory()

        print json.dumps(self.inventory);

    def build_inventory(self):
        inventory = self.dynamic_groups(group_name="target-hosts", env_var="TARGET_HOSTS").copy()
        inventory.update(self.dynamic_groups(group_name="coordinating-nodes", env_var="COORDINATING_NODES"))
        inventory.update(
            {
                '_meta': {
                    'hostvars': {}
                }
            }
        )

        return inventory

    def dynamic_groups(self, group_name=None, env_var=None):
        if group_name is None or env_var is None or env_var not in os.environ:
            return {}
        else:
            group_hosts = os.environ[env_var]

        return {
            group_name: {
                'hosts': group_hosts.split(","),
                'vars': {
                    'ansible_ssh_user': ANSIBLE_USER,
                    'ansible_ssh_private_key_file': ANSIBLE_SSH_PRIVATE_KEY_FILE
                }
            }
        }

    def empty_inventory(self):
        return {'_meta': {'hostvars': {}}}

    def read_cli_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--list', action = 'store_true')
        parser.add_argument('--host', action = 'store')
        parser.add_argument('--refresh', action = 'store_true')
        self.args = parser.parse_args()

Inventory()
