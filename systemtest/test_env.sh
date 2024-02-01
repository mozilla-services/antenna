#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# This runs the system tests. It expects the following things to exist:
#
# * "python3" available in PATH
#
# To run this from the root of this repository, do this:
#
#     $ ./tests/systemtests/run_tests.sh
#
# Set POSTURL to the url to post to.
#
# Set NONGINX=1 if you're running against a local dev environment. This
# will skip tests that require nginx.

set -e

USAGE="Usage: test_env.sh [local|stage]"

if [[ $# -eq 0 ]]; then
    echo "${USAGE}"
    exit 1;
fi

case $1 in
    "local")
        # Whether or not we're running behind nginx and to run nginx tests
        export NGINX_TESTS=0
        # Whether or not we can verify the file was saved (need access to S3)
        export POST_CHECK=1
        # The host to submit to
        export HOST=http://web:8000/
        ;;
    "stage")
        export NGINX_TESTS=1
        export POST_CHECK=0
        export HOST=https://crash-reports.allizom.org/
        ;;
    *)
        echo "${USAGE}"
        exit 1;
        ;;
esac

echo "HOST: ${HOST}"
echo "NGINX_TESTS: ${NGINX_TESTS}"

# make sure to run systemtest even if this script is called from the git root
cd "$(dirname "$0")/.."

pytest -vv
