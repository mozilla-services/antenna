#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Usage: bin/run_setup.sh
#
# Wipes and then sets up Pub/Sub and S3 services.
#
# This should be called from inside a container.

set -euo pipefail

# Wait for services to be ready
echo "Waiting for ${CRASHMOVER_CRASHSTORAGE_ENDPOINT_URL} ..."
urlwait "${CRASHMOVER_CRASHSTORAGE_ENDPOINT_URL}" 10
echo "Waiting for ${CRASHMOVER_CRASHPUBLISH_ENDPOINT_URL} ..."
urlwait "${CRASHMOVER_CRASHPUBLISH_ENDPOINT_URL}" 10

echo "Delete and create S3 bucket..."
python ./bin/s3_cli.py delete "${CRASHMOVER_CRASHSTORAGE_BUCKET_NAME}"
python ./bin/s3_cli.py create "${CRASHMOVER_CRASHSTORAGE_BUCKET_NAME}"
python ./bin/s3_cli.py list_buckets

echo "Delete and create SQS queue..."
python ./bin/sqs_cli.py delete "${CRASHMOVER_CRASHPUBLISH_QUEUE_NAME}"
python ./bin/sqs_cli.py create "${CRASHMOVER_CRASHPUBLISH_QUEUE_NAME}"
