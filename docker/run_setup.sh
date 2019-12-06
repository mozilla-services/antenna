#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: docker/run_setup.sh
#
# Wipes and then sets up Pub/Sub and S3 services.
#
# This should be called from inside a container.

set -e

echo "Delete and create S3 bucket..."
python ./bin/s3_cli.py delete "${CRASHSTORAGE_BUCKET_NAME}"
python ./bin/s3_cli.py create "${CRASHSTORAGE_BUCKET_NAME}"
python ./bin/s3_cli.py list_buckets

echo "Delete and create Pub/Sub topic..."
python ./bin/pubsub_cli.py delete_topic "${CRASHPUBLISH_PROJECT_ID}" "${CRASHPUBLISH_TOPIC_NAME}"
python ./bin/pubsub_cli.py create_topic "${CRASHPUBLISH_PROJECT_ID}" "${CRASHPUBLISH_TOPIC_NAME}"
python ./bin/pubsub_cli.py create_subscription "${CRASHPUBLISH_PROJECT_ID}" "${CRASHPUBLISH_TOPIC_NAME}" "${CRASHPUBLISH_SUBSCRIPTION_NAME}"
python ./bin/pubsub_cli.py list_topics "${CRASHPUBLISH_PROJECT_ID}"

echo "Delete and create SQS queue..."
python ./bin/sqs_cli.py delete "${CRASHPUBLISH_QUEUE_NAME}"
python ./bin/sqs_cli.py create "${CRASHPUBLISH_QUEUE_NAME}"
