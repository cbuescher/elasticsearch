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


# see http://stackoverflow.com/a/246128
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
NIGHT_RALLY_HOME="$( cd -P "$( dirname "$SOURCE" )" && pwd )"


SELF_UPDATE=NO

for i in "$@"
do
case $i in
    --override-src-dir=*)
    OVERRIDE_SRC_DIR="${i#*=}"
    shift # past argument=value
    ;;
    --self-update)
    SELF_UPDATE=YES
    shift # past argument with no value
    ;;
    *)
    echo "unknown"        # unknown option
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

if [ -n "${OVERRIDE_SRC_DIR}" ]
then
	NIGHT_RALLY_OVERRIDE="--override-src-dir=${OVERRIDE_SRC_DIR}"
else
	NIGHT_RALLY_OVERRIDE=""
fi


# We invoke it currently with the current (UTC) timestamp. This determines the version to checkout
python3  ${NIGHT_RALLY_HOME}/night_rally.py --effective-start-date="`date -u "+%Y-%m-%d %H:%M:%S"`" ${NIGHT_RALLY_OVERRIDE}

echo "Uploading results to $S3_ROOT_BUCKET"
#s3cmd sync --guess-mime-type -P ~/.rally/benchmarks/reports/out/ ${S3_ROOT_BUCKET}/
aws s3 cp --recursive --acl "public-read" "~/.rally/benchmarks/reports/out/" "${S3_ROOT_BUCKET}/"