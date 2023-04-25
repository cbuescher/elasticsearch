#!/usr/bin/env bash

set -eo pipefail

export HOME=/var/lib/jenkins
cd $HOME

source ~/.profile
export PATH=$HOME/bin:$HOME/.local/bin:$PATH

night_rally --self-update --mode="$MODE" --version="$VERSION" --runtime-jdk="$RUNTIME_JDK" --release-license="$RELEASE_LICENSE" --target-host="$TARGET_HOSTS" --race-configs="$RACE_CONFIGS" --effective-start-date="$EFFECTIVE_START_DATE"
