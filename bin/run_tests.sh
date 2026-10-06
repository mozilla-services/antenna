#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Usage: bin/run_tests.sh
#
# Runs tests.
#
# This should be called from inside a container and after the dependent
# services have been launched. It depends on:
#
# * elasticsearch
# * postgresql

set -euo pipefail

echo ">>> pytest"
# Set up environment variables

export PYTHONPATH=/app/:${PYTHONPATH:-}
PYTEST="$(which pytest)"

# Wait for services to be ready (both have the same endpoint url)
urlwait "http://${PUBSUB_EMULATOR_HOST}" 10
urlwait "${STORAGE_EMULATOR_HOST}/storage/v1/b" 10

if [ -f metrics_emitted.txt ]; then
    rm metrics_emitted.txt
fi

# Run tests
exec "${PYTEST}" "$@"
