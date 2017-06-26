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


S3_ROOT_BUCKET="s3://elasticsearch-benchmarks.elastic.co"
LOCAL_REPORT_ROOT="${HOME}/.rally/benchmarks/reports"
LOCAL_REPORT_OUT="${LOCAL_REPORT_ROOT}/out"

# see http://stackoverflow.com/a/246128
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ ${SOURCE} != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
NIGHT_RALLY_HOME="$( cd -P "$( dirname "$SOURCE" )" && pwd )"


ANSIBLE_ALL_TAGS=(encryption-at-rest initialize-data-disk trim)
ANSIBLE_SKIP_TAGS=( )
ANSIBLE_SKIP_TAGS_STRING=""
SELF_UPDATE=NO
DRY_RUN=NO
SKIP_S3=NO
# We invoke Rally with the current (UTC) timestamp. This determines the version to checkout.
START_DATE=`date -u "+%Y-%m-%d %H:%M:%S"`
MODE="nightly"
RELEASE="master"
# only needed for ad-hoc benchmarks
REVISION="latest"
REPLACE_RELEASE=${RELEASE}
TARGET_HOST="localhost:9200"
TAG=""


# https://stackoverflow.com/a/8574392
containsElement () {
    local e
    for e in "${@:2}"; do [[ "$e" == "$1" ]] && return 0; done
    return 1
}

for i in "$@"
do
case ${i} in
    --override-src-dir=*)
    OVERRIDE_SRC_DIR="${i#*=}"
    shift # past argument=value
    ;;
    --override-effective-start-date=*)
    START_DATE="${i#*=}"
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
    --skip-s3)
    SKIP_S3=YES
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
    --replace-release=*)
    REPLACE_RELEASE="${i#*=}"
    shift # past argument=value
    ;;
    --tag=*)
    TAG="${i#*=}"
    shift # past argument=value
    ;;
    --target-host=*)
    TARGET_HOST="${i#*=}"
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

############### TO BE CONVERTED TO A FUNCTION ###################
OLDIFS=$IFS
IFS=','

for fixture in $FIXTURES
do
    if ! containsElement "$fixture" "${ANSIBLE_ALL_TAGS[@]}"; then
        ANSIBLE_SKIP_TAGS+=("$fixture")
    fi
done
IFS=$OLDIFS

# join tags with a comma (,) character
ANSIBLE_SKIP_TAGS_STRING=$(printf ",%s" "${ANSIBLE_SKIP_TAGS[@]}")
ANSIBLE_SKIP_TAGS_STRING=${ANSIBLE_SKIP_TAGS_STRING:1}

pushd . >/dev/null 2>&1

cd ${NIGHT_RALLY_HOME}/fixtures/ansible
ansible-playbook -i inventory/production -u rally playbooks/update-rally.yml
ansible-playbook -i inventory/production -u rally playbooks/setup.yml --skip-tags $ANSIBLE_SKIP_TAGS_STRING

popd >/dev/null 2>&1

if [ -n "${OVERRIDE_SRC_DIR}" ]
then
    NIGHT_RALLY_OVERRIDE="--override-src-dir=${OVERRIDE_SRC_DIR}"
else
    NIGHT_RALLY_OVERRIDE=""
fi

if [ ${DRY_RUN} == YES ]
then
    NIGHT_RALLY_DRY_RUN="--dry-run"
else
    NIGHT_RALLY_DRY_RUN=""
fi

# We need to pull down the current state of all reports from the S3 bucket as night_rally might be run on different nodes each day
if [ ${SKIP_S3} == NO ]
then
    echo "Syncing previous results from ${S3_ROOT_BUCKET}"
    if [ ${DRY_RUN} == NO ]
    then
        aws s3 sync "${S3_ROOT_BUCKET}/" "${LOCAL_REPORT_OUT}/"
    fi
else
    echo "Skipping download from ${S3_ROOT_BUCKET}"
fi

# Night Rally is *always* the master for assets
ASSET_SOURCE="${NIGHT_RALLY_HOME}/external/pages/default/*"
ASSET_TARGET="${LOCAL_REPORT_OUT}/"
echo "Copying most recent assets from ${ASSET_SOURCE} to ${ASSET_TARGET}"
if [ ${DRY_RUN} == NO ]
then
    cp -R ${ASSET_SOURCE} ${ASSET_TARGET}
fi

# Only copy if the target directory does not exist! Otherwise we overwrite csv files with data.
ADHOC_TEMPLATE_ASSET_SOURCE="${NIGHT_RALLY_HOME}/external/pages/adhoc/*"
ADHOC_TEMPLATE_ASSET_TARGET="${LOCAL_REPORT_ROOT}/templates"
if [ ! -d "${ADHOC_TEMPLATE_ASSET_TARGET}" ]; then
    echo "Copying most recent adhoc benchmark templates from ${ADHOC_TEMPLATE_ASSET_SOURCE} to ${ADHOC_TEMPLATE_ASSET_TARGET}"
    if [ ${DRY_RUN} == NO ]
    then
        mkdir -p ${ADHOC_TEMPLATE_ASSET_TARGET}
        cp -R ${ADHOC_TEMPLATE_ASSET_SOURCE} ${ADHOC_TEMPLATE_ASSET_TARGET}
    fi
fi



#****************************
# START NO FAIL
#****************************
set +e
# Avoid failing before we transferred all results. Usually only a single benchmark trial run fails but lots of other succeed.
python3 ${NIGHT_RALLY_HOME}/night_rally.py --target-host=${TARGET_HOST} --effective-start-date="${START_DATE}" ${NIGHT_RALLY_OVERRIDE} --mode=${MODE} ${NIGHT_RALLY_DRY_RUN} --revision="${REVISION}" --release="${RELEASE}" --replace-release="${REPLACE_RELEASE}" --tag="${TAG}"
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

if [ ${SKIP_S3} == NO ]
then
    echo "Uploading results to ${S3_ROOT_BUCKET}"
    if [ ${DRY_RUN} == NO ]
    then
        #s3cmd sync --guess-mime-type -P ~/.rally/benchmarks/reports/out/ ${S3_ROOT_BUCKET}/
        # --acl "public-read"           - let everyone read the report files
        # --cache-control max-age=86400 - ensure that report files expire after one day so users always see fresh data
        aws s3 sync --acl "public-read" --cache-control max-age=86400 "${LOCAL_REPORT_OUT}/" "${S3_ROOT_BUCKET}/"
    fi
else
    echo "Skipping upload from results to ${S3_ROOT_BUCKET}"
fi

# Exit with the same exit code as night_rally.py
exit ${exit_code}
