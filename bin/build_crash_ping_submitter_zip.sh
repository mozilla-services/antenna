#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Usage: bin/build_crash_ping_submitter_zip.sh [OUTPUT]
#
# Builds the crash ping submitter cloud function source zip.
#
# The GCP Python buildpack expects main.py and requirements.txt at the root of
# the archive, so this puts them in a temporary directory instead of zipping
# the source tree in place. requirements.txt is generated here rather than
# committed, so there is nothing that can drift out of date with uv.lock.
#
# NOTE: CI names the uploaded object after the git tree sha of
# crash_ping_submitter/, which does not cover this script. If you change what
# goes into the zip without changing anything under crash_ping_submitter/, the
# object for the current tree sha already exists and will not be replaced.
# Touch a file in that directory to get a new one.
#
# This only needs uv and python, so it runs both inside a container (locally,
# via just) and directly on the runner (in CI).

set -euo pipefail

SRC_DIR="crash_ping_submitter"
OUTPUT="${1:-dist/crash-ping-submitter.zip}"
OUTPUT_PATH="$(pwd)/${OUTPUT}"

TMP_ZIP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_ZIP_DIR}"' EXIT

echo ">>> generating requirements.txt from ${SRC_DIR}/uv.lock"
# --directory  export the function's own project rather than Antenna's
# --locked     fail if uv.lock is out of date with pyproject.toml
# --no-dev     keep pytest and its dependencies out of the deployed function
# --quiet      uv writes the file to stdout as well as to -o
uv export \
    --directory "${SRC_DIR}" \
    --locked \
    --no-dev \
    --quiet \
    -o "${TMP_ZIP_DIR}/requirements.txt"

cp "${SRC_DIR}/main.py" "${TMP_ZIP_DIR}/"

mkdir -p "$(dirname "${OUTPUT_PATH}")"
rm -f "${OUTPUT_PATH}"

echo ">>> building ${OUTPUT}"
# There is no zip binary in the container, so use the standard library one.
cd "${TMP_ZIP_DIR}"
python -m zipfile -c "${OUTPUT_PATH}" main.py requirements.txt

python -m zipfile -l "${OUTPUT_PATH}"
