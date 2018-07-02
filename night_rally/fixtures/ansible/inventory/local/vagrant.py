#!/usr/bin/env python
"""
Vagrant external inventory script. Automatically finds the IP of the booted vagrant vm(s), and
returns it under the host group 'vagrant'

Example Vagrant configuration using this script:

    config.vm.provision :ansible do |ansible|
      ansible.playbook = "./provision/your_playbook.yml"
      ansible.inventory_file = "./provision/inventory/vagrant.py"
      ansible.verbose = true
    end

requires paramiko

"""

# Copyright (C) 2013  Mark Mandel <mark@compoundtheory.com>
#               2015  Igor Khomyakov <homyakov@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#
# Thanks to the spacewalk.py inventory script for giving me the basic structure
# of this.
#

import sys
import os.path
import subprocess
import re
from paramiko import SSHConfig
from cStringIO import StringIO
from optparse import OptionParser
from collections import defaultdict
from time import time
try:
    import json
except:
    import simplejson as json

_group = 'vagrant'  # a default group
_ssh_to_ansible = [('user', 'ansible_user'),
                   ('hostname', 'ansible_host'),
                   ('identityfile', 'ansible_ssh_private_key_file'),
                   ('port', 'ansible_port')]

cache_dir = os.path.expanduser('~/.ansible/tmp')
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

cache_file = cache_dir + "/ansible-vagrant.cache"
cache_max_age = 900

docker_capable_hosts = ['ubuntu-16.04', 'ubuntu-14.04', 'centos-7', 'oraclelinux-7', 'fedora', 'debian-8', 'opensuse']

# Options
# ------------------------------

parser = OptionParser(usage="%prog [options] --list | --host <machine> | --refresh-cache")
parser.add_option('--list', default=False, dest="list", action="store_true",
                  help="Produce a JSON consumable grouping of Vagrant servers for Ansible")
parser.add_option('--host', default=None, dest="host",
                  help="Generate additional host specific details for given host for Ansible")
parser.add_option('--refresh-cache', action='store_true', default=False,
                  help='Force a refresh of the inventory cache file')
(options, args) = parser.parse_args()

#
# helper functions
#


# get all the ssh configs for all boxes in an array of dictionaries.
def get_ssh_config():
    return {k: get_a_ssh_config(k) for k in list_running_boxes()}


# list all the running boxes
def list_running_boxes():
    output = subprocess.check_output(["vagrant", "status"]).split('\n')

    boxes = []

    for line in output:
        matcher = re.search("([^\s]+)[\s]+running \(.+", line)
        if matcher:
            boxes.append(matcher.group(1))

    return boxes


# get the ssh config for a single box
def get_a_ssh_config(box_name):
    """Gives back a map of all the machine's ssh configurations"""

    output = subprocess.check_output(["vagrant", "ssh-config", box_name])
    config = SSHConfig()
    config.parse(StringIO(output))
    host_config = config.lookup(box_name)

    # set windows hosts to connect via WinRM rather than ssh
    if box_name.startswith('windows'):
        ports = subprocess.check_output(["vagrant", "port", box_name]).split('\n')

        # search for the host port that's forwarded to the WinRM port (5986) on the guest
        for line in ports:
            matcher = re.search("^\s+5986 \(guest\).*\s(\d+)", line)
            if matcher:
                host_config['port'] = matcher.group(1)

    # man 5 ssh_config:
    # > It is possible to have multiple identity files ...
    # > all these identities will be tried in sequence.
    for id in host_config['identityfile']:
        if os.path.isfile(id):
            host_config['identityfile'] = id

    return {v: host_config[k] for k, v in _ssh_to_ansible}


def vagrant_groups(metadata):
    groups = defaultdict(list)

    for host, _ in metadata.iteritems():
        try:
            group = host.split('.')[1]
            groups[group].append(host)
        except IndexError:
            pass

    return groups


# check if the cache file should be considered valid
def cache_is_invalid():
    """Determines if the cache file has expired, or if it is still valid"""

    if os.environ.get('VAGRANT_FORCE_REFRESH_CACHE') == 'true':
        return True

    if os.path.isfile(cache_file):
        mod_time = os.path.getmtime(cache_file)
        current_time = time()
        if (mod_time + cache_max_age) > current_time:
            return False

    return True


# update the cache file with the running server info
def update_the_cache():
    """Writes the server data in JSON format to the cache file"""
    ssh_config = get_ssh_config()
    meta = defaultdict(dict)
    all_hostnames = []

    for host in ssh_config:
        meta['hostvars'][host] = ssh_config[host]

        all_hostnames.append(host)

    json_data = json.dumps(
        dict({
            _group: list(ssh_config.keys()),
            'elasticsearch-ci-slaves-macrobenchmarks': [i for i in all_hostnames if 'coordinator' in i],
            'macrobenchmarks-targets': [i for i in all_hostnames if 'target' in i],
            'memorybenchmarks': [i for i in all_hostnames if 'memorybenchmark' in i],
            '_meta': meta
        }, **vagrant_groups(ssh_config)))
    cache = open(cache_file, 'w')
    cache.write(json_data)
    cache.close()


# List out servers that vagrant has running
# ------------------------------
if options.list:
    if options.refresh_cache or cache_is_invalid():
        update_the_cache()

    with open(cache_file, 'r') as cache:
        print cache.read()
    sys.exit(0)

# Get out the host details
# ------------------------------
elif options.host:
    print(json.dumps(get_a_ssh_config(options.host)))
    sys.exit(0)

# Force a refresh of the cache and print nothing
# ------------------------------
elif options.refresh_cache:
    update_the_cache()
    sys.exit(0)

# Print out help
# ------------------------------
else:
    parser.print_help()
    sys.exit(0)
