#!/usr/bin/env bash

#################################################################################
#
# rallyd restart job. This script enforces a daily restart of rallyd.
#
# As we have automatic updates but rallyd runs continuously, we need to restart
# it in order to get the latest updates.
#
#################################################################################

if [ "$#" -ne 2 ]; then
    echo "Usage: $(basename "$0") node-ip coordinator-ip"
    exit 1
fi

echo "Stopping rallyd"
/var/lib/jenkins/bin/rallyd stop
sleep 5
# just in case...
echo "Killing all Rally daemon processes"
killall -9 esrallyd
echo "Starting rallyd with node IP $1 and coordinator ip $2"
/var/lib/jenkins/bin/rallyd start --node-ip $1 --coordinator-ip $2