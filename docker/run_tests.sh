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

LOCALSTACK_S3_URL=http://localstack-s3:5000
PUBSUB_URL=http://pubsub:5010

export PYTHONPATH=/app/:$PYTHONPATH
PYTEST="$(which pytest)"
PYTHON="$(which python)"

# Wait for services to be ready
urlwait "${LOCALSTACK_S3_URL}" 10
urlwait "${PUBSUB_URL}" 10

# Run tests
"${PYTEST}"
