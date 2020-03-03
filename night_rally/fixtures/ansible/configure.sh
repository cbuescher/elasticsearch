#!/usr/bin/env bash

set -e

SOURCE="${BASH_SOURCE[0]}"
while [[ -h $SOURCE ]]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ ${SOURCE} != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
SCRIPT_HOME="$( cd -P "$( dirname "$SOURCE" )" && pwd )"

cd ${SCRIPT_HOME}

export RALLY_METRICS_STORE_CREDENTIAL_PATH=${RALLY_METRICS_STORE_CREDENTIAL_PATH:-"/secret/rally/cloud/nightly-rally-metrics"}
# attempt to read so we can determine early on whether the user is logged in
set +e
vault read ${RALLY_METRICS_STORE_CREDENTIAL_PATH} > /dev/null 2>&1
exit_code=$?
set -e
if [[ ${exit_code} -ne 0 ]]; then
    echo "Failed to read from ${RALLY_METRICS_STORE_CREDENTIAL_PATH}. Please log in to Vault."
    exit 1
fi

# Workaround for https://github.com/ansible/ansible/issues/31869 which is
# basically a Python deficiency (see
# http://sealiesoftware.com/blog/archive/2017/6/5/Objective-C_and_fork_in_macOS_1013.html
# for details).
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

ansible-playbook --connection=local playbooks/configure-rally.yml --extra-vars="rally_environment=nightly local_setup=true"
ansible-playbook --connection=local playbooks/configure-rally.yml --extra-vars="rally_environment=release local_setup=true"
unset OBJC_DISABLE_INITIALIZE_FORK_SAFETY
cd - > /dev/null
