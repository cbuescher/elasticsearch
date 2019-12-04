#!/usr/bin/env bash

###############################################################################
#
# Night Rally: Nightly macrobenchmarks for Elasticsearch
#
# This is the main entry point for running a night rally. The script
# self-updates before invoking the actual benchmark driver. It assumes
# that this very script does not change significantly (as the updated
# version would only be invoked with the *next* nightly benchmark run).
#
###############################################################################


# fail this script immediately if any command fails with a non-zero exit code
set -e

# see http://stackoverflow.com/a/246128
SOURCE="${BASH_SOURCE[0]}"
while [[ -h $SOURCE ]]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ ${SOURCE} != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
NIGHT_RALLY_HOME="$( cd -P "$( dirname "$SOURCE" )" && pwd )"

# Interactive users are required to be logged in already, others (like Jenkins) will expose VAULT_SECRET_ID env variable.
if [[ -n $VAULT_SECRET_ID && -n $VAULT_ROLE_ID ]]; then
    export VAULT_TOKEN=$( curl -s -X POST -H "Content-Type: application/json" -L -d "{\"role_id\":\"$VAULT_ROLE_ID\",\"secret_id\":\"$VAULT_SECRET_ID\"}" $VAULT_ADDR/v1/auth/approle/login | jq -r '.auth.client_token')
    unset VAULT_SECRET_ID
    unset VAULT_ROLE_ID
fi
export RALLY_METRICS_STORE_CREDENTIAL_PATH=${RALLY_METRICS_STORE_CREDENTIAL_PATH:-"/secret/rally/cloud/nightly-rally-metrics"}

ANSIBLE_ALL_TAGS=(check-drive-health encryption-at-rest initialize-data-disk trim drop-caches)
ANSIBLE_SKIP_TAGS=( )
ANSIBLE_SKIP_TAGS_STRING=""
# Don't update night-rally by default, unless specified by env var
SELF_UPDATE=${SELF_UPDATE:-NO}
DRY_RUN=NO
SKIP_ANSIBLE=NO
# Optionally, allow skipping Rally's auto-update mechanism. Applicable in Vagrant only.
SKIP_RALLY_UPDATE=${SKIP_RALLY_UPDATE:-NO}
# We invoke Rally with the current (UTC) timestamp. This determines the version to checkout.
EFFECTIVE_START_DATE=`date -u "+%Y-%m-%d %H:%M:%S"`
# Deploy different Cloud credentials when running inside Vagrant
IN_VAGRANT=${IN_VAGRANT:NO}
MODE="nightly"
TEST_MODE=${TEST_MODE:NO}
VERSION="master"
RELEASE_LICENSE=${RELEASE_LICENSE:-oss}
# only needed for ad-hoc benchmarks
REVISION="latest"
RUNTIME_JDK=${RUNTIME_JDK:-"11"}
TARGET_HOST="localhost:9200"
RELEASE_X_PACK_COMPONENTS=${RELEASE_X_PACK_COMPONENTS:-""}
RACE_CONFIGS_FILE=""
TELEMETRY=""
TELEMETRY_PARAMS=""
RALLY_ENVIRONMENT=""

for i in "$@"
do
case ${i} in
    --effective-start-date=*)
    OVERRIDE_START_DATE="${i#*=}"
    EFFECTIVE_START_DATE=${OVERRIDE_START_DATE:-${EFFECTIVE_START_DATE}}
    shift # past argument=value
    ;;
    --self-update)
    SELF_UPDATE=YES
    shift # past argument with no value
    ;;
    --skip-rally-update)
    SKIP_RALLY_UPDATE=YES
    shift # past argument with no value
    ;;
    --dry-run)
    DRY_RUN=YES
    shift # past argument with no value
    ;;
    --skip-ansible)
    SKIP_ANSIBLE=YES
    shift # past argument with no value
    ;;
    --mode=*)
    MODE="${i#*=}"
    shift # past argument=value
    ;;
    --environment=*)
    RALLY_ENVIRONMENT="${i#*=}"
    shift # past argument=value
    ;;
    --test-mode)
    TEST_MODE=YES
    shift # past argument with no value
    ;;
    --in-vagrant=*)
    IN_VAGRANT=YES
    shift # past argument=value
    ;;
    --revision=*)
    REVISION="${i#*=}"
    shift # past argument=value
    ;;
    --runtime-jdk=*)
    RUNTIME_JDK="${i#*=}"
    shift # past argument=value
    ;;
    --version=*)
    VERSION="${i#*=}"
    shift # past argument=value
    ;;
    --release-license=*)
    RELEASE_LICENSE="${i#*=}"
    shift # past argument=value
    ;;
    --target-host=*)
    TARGET_HOST="${i#*=}"
    shift # past argument=value
    ;;
    --race-configs=*)
    RACE_CONFIGS_FILE="${i#*=}"
    shift # past argument=value
    ;;
    --telemetry=*)
    TELEMETRY="${i#*=}"
    shift # past argument=value
    ;;
    --telemetry-params=*)
    TELEMETRY_PARAMS="${i#*=}"
    shift # past argument=value
    ;;
    --release-x-pack-components=*)
    RELEASE_X_PACK_COMPONENTS="${i#*=}"
    shift # past argument=value
    ;;
    *)
    echo "unknown command line option [${i}] passed to night_rally"
    exit 1
    ;;
esac
done

if [[ -z "$RALLY_ENVIRONMENT" ]]
then
  # If not explicitly set, Rally environment is derived from the first token of
  # $MODE, tokenized by ":" (e.g. for "release:docker" the environment is "release").
  RALLY_ENVIRONMENT=${MODE%:*}
fi

if [[ $SELF_UPDATE == YES ]]
then
    pushd . >/dev/null 2>&1
    cd ${NIGHT_RALLY_HOME} >/dev/null 2>&1

    # see http://unix.stackexchange.com/a/155077
    if output=$(git status --porcelain) && [ -z "$output" ] && on_master=$(git rev-parse --abbrev-ref HEAD) && [ "$on_master" == "master" ]
    then
      # Working directory clean -> we assume this is a user that is not actively developing night rally and just upgrade it every time it is invoked
      echo "Auto-updating Night Rally"

      # this will fail if the user is offline
      git fetch origin --quiet
      git rebase origin/master --quiet

      source install.sh

    # else
      # Uncommitted changes - don't upgrade, just run
    fi

    popd >/dev/null 2>&1
fi

if [[ $SKIP_ANSIBLE == NO ]]
then
    # $MODE may contain the `encryption-at-rest` fixture
    # TODO: consider removing this and expecting encryption-at-rest to be explicitly set in fixtures when we
    # have an automatic invocation script.
    ALL_FIXTURES=${FIXTURES}
    if [[ ${MODE} == *encryption-at-rest* && ${FIXTURES} != *encryption-at-rest* ]]; then
        ALL_FIXTURES="${FIXTURES},encryption-at-rest"
    fi

    for fixture in "${ANSIBLE_ALL_TAGS[@]}"
    do
        if [[ ${ALL_FIXTURES} != *$fixture* ]] ; then
            ANSIBLE_SKIP_TAGS+=("$fixture")
        fi
    done

    if [[ ${#ANSIBLE_SKIP_TAGS[@]} == 0 ]]; then
        ANSIBLE_SKIP_TAGS_STRING=""
    else
        # join tags with a comma (,) character
        ANSIBLE_SKIP_TAGS_STRING=$(printf ",%s" "${ANSIBLE_SKIP_TAGS[@]}")
        ANSIBLE_SKIP_TAGS_STRING=${ANSIBLE_SKIP_TAGS_STRING:1}
        ANSIBLE_SKIP_TAGS_STRING="--skip-tags $ANSIBLE_SKIP_TAGS_STRING"
    fi

    echo "About to run ansible-playbook ... with '$ANSIBLE_SKIP_TAGS_STRING'"
    if [[ $DRY_RUN == NO ]]
    then
        pushd . >/dev/null 2>&1

        cd ${NIGHT_RALLY_HOME}/night_rally/fixtures/ansible
        ansible-playbook -i inventory/production -u rally playbooks/update-rally.yml --extra-vars="rally_environment=${RALLY_ENVIRONMENT} in_vagrant=${IN_VAGRANT} skip_rally_update=${SKIP_RALLY_UPDATE}"
        ansible-playbook -i inventory/production -u rally playbooks/check-drive-health.yml ${ANSIBLE_SKIP_TAGS_STRING} --extra-vars="in_vagrant=${IN_VAGRANT}"
        ansible-playbook -i inventory/production -u rally playbooks/setup.yml ${ANSIBLE_SKIP_TAGS_STRING}

        popd >/dev/null 2>&1
    fi
else
    echo "Skipping Ansible execution."
fi

if [[ $DRY_RUN == YES ]]
then
    NIGHT_RALLY_DRY_RUN="--dry-run"
else
    NIGHT_RALLY_DRY_RUN=""
fi

if [[ $SKIP_ANSIBLE == YES ]]
then
    SKIP_ANSIBLE_PARAM="--skip-ansible"
else
    SKIP_ANSIBLE_PARAM=""
fi

NIGHT_RALLY_COMMAND="es-night-rally \
    --target-host=${TARGET_HOST} \
    --effective-start-date=\"${EFFECTIVE_START_DATE}\" \
    --mode=${MODE} \
    --environment=${RALLY_ENVIRONMENT} \
    ${NIGHT_RALLY_DRY_RUN} \
    ${SKIP_ANSIBLE_PARAM} \
    --runtime-jdk=\"${RUNTIME_JDK}\" \
    --revision=\"${REVISION}\" \
    --version=\"${VERSION}\" \
    --release-license=\"${RELEASE_LICENSE}\" \
    --release-x-pack-components=\"${RELEASE_X_PACK_COMPONENTS}\" \
    --race-configs=\"${RACE_CONFIGS_FILE}\" \
    --telemetry=\"${TELEMETRY}\" \
    --telemetry-params=\"${TELEMETRY_PARAMS}\""

#****************************
# START NO FAIL
#****************************
set +e
# Avoid failing before cleanup. Usually only a single benchmark trial run fails but lots of other succeed.
if [[ ${TEST_MODE} == YES ]]; then
    NIGHT_RALLY_COMMAND="${NIGHT_RALLY_COMMAND} --test-mode"
fi

eval ${NIGHT_RALLY_COMMAND}
exit_code=$?

echo "Killing any lingering Rally processes"
# Also don't fail if there are no lingering Rally processes
if [[ $DRY_RUN == NO ]]
then
    killall -q esrally
fi

#****************************
# END NO FAIL
#****************************
set -e

# Exit with the same exit code as night_rally.py
exit ${exit_code}
