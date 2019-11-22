#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Runs tests.
#
# This should be called from inside a container and after the dependent
# services have been launched. It depends on:
#
# * elasticsearch
# * postgresql
# * pubsub

# Failures should cause setup to fail
set -v -e -x

echo ">>> pytest"
# Set up environment variables

export PYTHONPATH=/app/:$PYTHONPATH
PYTEST="$(which pytest)"
PYTHON="$(which python)"

# Wait for services to be ready
urlwait "${CRASHSTORAGE_ENDPOINT_URL}" 10
urlwait "http://${PUBSUB_EMULATOR_HOST}" 10
urlwait "http://localstack-sqs:4576" 10

# Run tests
"${PYTEST}"
