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
while [ -h "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ ${SOURCE} != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
NIGHT_RALLY_HOME="$( cd -P "$( dirname "$SOURCE" )" && pwd )"


ANSIBLE_ALL_TAGS=(encryption-at-rest initialize-data-disk trim drop-caches)
ANSIBLE_SKIP_TAGS=( )
ANSIBLE_SKIP_TAGS_STRING=""
SELF_UPDATE=NO
DRY_RUN=NO
SKIP_ANSIBLE=NO
# We invoke Rally with the current (UTC) timestamp. This determines the version to checkout.
EFFECTIVE_START_DATE=`date -u "+%Y-%m-%d %H:%M:%S"`
MODE="nightly"
RELEASE="master"
# only needed for ad-hoc benchmarks
REVISION="latest"
TARGET_HOST="localhost:9200"
PLUGINS=""
TRACKS_FILE=""
TELEMETRY=""
TELEMETRY_PARAMS=""

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
    --revision=*)
    REVISION="${i#*=}"
    shift # past argument=value
    ;;
    --release=*)
    RELEASE="${i#*=}"
    shift # past argument=value
    ;;
    --target-host=*)
    TARGET_HOST="${i#*=}"
    shift # past argument=value
    ;;
    --tracks=*)
    TRACKS_FILE="${i#*=}"
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
    --elasticsearch-plugins=*)
    PLUGINS="${i#*=}"
    shift # past argument=value
    ;;
    *)
    echo "unknown command line option passed to night_rally"
    exit 1
    ;;
esac
done

if [ ${SELF_UPDATE} == YES ]
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
    # else
      # Uncommitted changes - don't upgrade, just run
    fi

    popd >/dev/null 2>&1
fi

if [ ${SKIP_ANSIBLE} == NO ]
then
    for fixture in "${ANSIBLE_ALL_TAGS[@]}"
    do
        if [[ ${FIXTURES} != *$fixture* ]] ; then
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
    if [ ${DRY_RUN} == NO ]
    then
        pushd . >/dev/null 2>&1

        cd ${NIGHT_RALLY_HOME}/fixtures/ansible
        ansible-playbook -i inventory/production -u rally playbooks/update-rally.yml --extra-vars="rally_environment=${MODE}"
        ansible-playbook -i inventory/production -u rally playbooks/setup.yml ${ANSIBLE_SKIP_TAGS_STRING}

        popd >/dev/null 2>&1
    fi
else
    echo "Skipping Ansible execution."
fi

if [ ${DRY_RUN} == YES ]
then
    NIGHT_RALLY_DRY_RUN="--dry-run"
else
    NIGHT_RALLY_DRY_RUN=""
fi

if [ ${SKIP_ANSIBLE} == YES ]
then
    SKIP_ANSIBLE_PARAM="--skip-ansible"
else
    SKIP_ANSIBLE_PARAM=""
fi

#****************************
# START NO FAIL
#****************************
set +e
# Avoid failing before we transferred all results. Usually only a single benchmark trial run fails but lots of other succeed.
python3 ${NIGHT_RALLY_HOME}/night_rally.py \
    --target-host=${TARGET_HOST} \
    --elasticsearch-plugins="${PLUGINS}" \
    --effective-start-date="${EFFECTIVE_START_DATE}" \
    --mode=${MODE} \
    ${NIGHT_RALLY_DRY_RUN} \
    ${SKIP_ANSIBLE_PARAM} \
    --fixtures="${FIXTURES}" \
    --revision="${REVISION}" \
    --release="${RELEASE}" \
    --tracks="${TRACKS_FILE}" \
    --telemetry="${TELEMETRY}" \
    --telemetry-params="${TELEMETRY_PARAMS}"

exit_code=$?

echo "Killing any lingering Rally processes"
# Also don't fail if there are no lingering Rally processes
if [ ${DRY_RUN} == NO ]
then
    killall -q esrally
fi

#****************************
# END NO FAIL
#****************************
set -e

# Exit with the same exit code as night_rally.py
exit ${exit_code}
