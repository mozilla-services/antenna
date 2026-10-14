#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Usage: crash_ping_submitter/build_zip.sh
#
# Builds the crash ping submitter cloud function source zip.
#
# The GCP Python buildpack expects main.py and requirements.txt at the root of
# the archive, so this puts them in a temporary directory instead of zipping
# the source tree in place. requirements.txt is generated here rather than
# committed, so there is nothing that can drift out of date with uv.lock.
#
# This only needs uv and python, so it runs both inside a container (locally,
# via just) and directly on the runner (in CI). Paths resolve relative to this
# script, so it doesn't matter what the working directory is.

set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_PATH="${SRC_DIR}/dist/crash-ping-submitter.zip"

TMP_ZIP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_ZIP_DIR}"' EXIT

echo ">>> generating requirements.txt from uv.lock"
# --directory  export the function's own project rather than Antenna's
# --locked     fail if uv.lock is out of date with pyproject.toml
# --no-dev     keep pytest and its dependencies out of the deployed function
# --quiet      uv writes the file to stdout as well as to -o
# --no-header  the header records the invoking command, including the random
#              temp path below, which would make the zip differ on every run
uv export \
    --directory "${SRC_DIR}" \
    --locked \
    --no-dev \
    --quiet \
    --no-header \
    -o "${TMP_ZIP_DIR}/requirements.txt"

cp "${SRC_DIR}/main.py" "${TMP_ZIP_DIR}/"

mkdir -p "$(dirname "${OUTPUT_PATH}")"
rm -f "${OUTPUT_PATH}"

echo ">>> building ${OUTPUT_PATH}"
# There is no zip binary in the container, so use the standard library one.
cd "${TMP_ZIP_DIR}"
python -m zipfile -c "${OUTPUT_PATH}" main.py requirements.txt

python -m zipfile -l "${OUTPUT_PATH}"
