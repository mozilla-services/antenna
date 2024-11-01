#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Usage: bin/run_setup.sh
#
# Wipes and then sets up Pub/Sub and GCS services.
#
# This should be called from inside a container.

set -euo pipefail

echo "Delete and create GCS bucket..."
gcs-cli delete "${CRASHMOVER_CRASHSTORAGE_BUCKET_NAME}"
gcs-cli create "${CRASHMOVER_CRASHSTORAGE_BUCKET_NAME}"
gcs-cli list_buckets

echo "Delete and create Pub/Sub topic..."
pubsub-cli delete_topic "${CRASHMOVER_CRASHPUBLISH_PROJECT_ID}" "${CRASHMOVER_CRASHPUBLISH_TOPIC_NAME}"
pubsub-cli create_topic "${CRASHMOVER_CRASHPUBLISH_PROJECT_ID}" "${CRASHMOVER_CRASHPUBLISH_TOPIC_NAME}"
pubsub-cli create_subscription "${CRASHMOVER_CRASHPUBLISH_PROJECT_ID}" "${CRASHMOVER_CRASHPUBLISH_TOPIC_NAME}" "${CRASHMOVER_CRASHPUBLISH_SUBSCRIPTION_NAME}"
pubsub-cli list_topics "${CRASHMOVER_CRASHPUBLISH_PROJECT_ID}"
