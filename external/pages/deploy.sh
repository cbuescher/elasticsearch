#!/usr/bin/env bash

# fail this script immediately if any command fails with a non-zero exit code
set -e

BUCKET_NAME="elasticsearch-benchmarks.elastic.co"
S3_ROOT_BUCKET="s3://${BUCKET_NAME}"
INDEX_PAGE_URL="https://${BUCKET_NAME}/index.html"

# see http://stackoverflow.com/a/246128
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ ${SOURCE} != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done

ASSET_SOURCE="$( cd -P "$( dirname "$SOURCE" )" && pwd )"

DRY_RUN=NO

for i in "$@"
do
case ${i} in
    --dry-run)
    DRY_RUN=YES
    shift # past argument with no value
    ;;
    *)
    echo "unknown command line option passed to ${0}"
    exit 1
    ;;
esac
done


echo "Uploading assets from [${ASSET_SOURCE}] to [${S3_ROOT_BUCKET}]"
if [ ${DRY_RUN} == YES ]
then
    AWS_DRY_RUN="--dryrun"
else
    AWS_DRY_RUN=""
fi
# --acl "public-read"           - let everyone read the assets
# --cache-control max-age=86400 - ensure that asset files expire after one day so users always see assets
aws s3 sync ${AWS_DRY_RUN} --acl "public-read" --cache-control max-age=86400 --exclude="deploy.sh" "${ASSET_SOURCE}/" "${S3_ROOT_BUCKET}/"

# Wait a bit for bucket to be consistent before we invalidate the cache
sleep 5

echo "Purging CDN cache for [${INDEX_PAGE_URL}]."
# The page is served via Fastly. Details on how to wipe away caches in:
# https://github.com/elastic/infra/issues/10695#issuecomment-521103380
curl -XPURGE ${INDEX_PAGE_URL}
