#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# For development, it probably makes sense to use one process (``--workers=1``)
# that can handle multiple concurrent connections (``--worker-connections=4``).
# The number of connections you want to handle simultaneously depends on your
# setup and all that.
#
# Make sure you use the ``gevent`` worker class (``--worker-class=gevent``).
# Otherwise it's not going to use the gevent WSGI app and then you're not going
# to be able to handle multiple network connections concurrently.

# If you're having problems getting the app to start, add ``--preload`` to the
# args list.

set -e

# First, create the bucket if it doesn't already exist
./bin/create_s3_bucket.py

# Create Pub/Sub topic if it doesn't already exist
./bin/pubsub_cli.py create_topic

# Launch the web-app
gunicorn \
    --reload \
    --bind=0.0.0.0:8000 \
    --workers=1 \
    --worker-connections=2 \
    --worker-class=gevent \
    --error-logfile=- \
    --access-logfile=- \
    --config=antenna/gunicornhooks.py \
    antenna.wsgi:application \
    --log-file -
