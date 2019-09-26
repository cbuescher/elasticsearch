#!/usr/bin/env bash

# This script is started interactively so we can ask the user to provide the missing bit
read -rsp "VAULT_SECRET_ID: " secret_id
export VAULT_ADDR=${VAULT_ADDR:-https://secrets.elastic.co:8200}
export VAULT_ROLE_ID="95c57192-a578-ac64-21c8-6d0bf5c06728"
export VAULT_SECRET_ID=$secret_id
export RALLY_METRICS_STORE_CREDENTIAL_PATH=${RALLY_METRICS_STORE_CREDENTIAL_PATH:-"/secret/rally/cloud/internal-rally-metrics"}
export COORDINATING_NODES=${COORDINATING_NODES:-"192.168.14.76"}
export TARGET_HOSTS=${TARGET_HOSTS:-"192.168.14.77,192.168.14.78,192.168.14.80"}

night_rally --self-update --mode=adhoc --environment=marathon --runtime-jdk=11 --target-host="$TARGET_HOSTS" --race-configs=resources/race-configs-longrunning.json --telemetry=gc
