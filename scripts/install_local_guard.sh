#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
git config --local core.hooksPath .githooks
echo "Installed local Git hooks from .githooks"
