#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Script that sets up the docker environment to run the tests in and runs the
# tests.

# Pass --shell to run a shell in the test container.

# Failures should cause setup to fail
set -v -e -x

# Set PS4 so it's easier to differentiate between this script and run_tests.sh
# running
PS4="+ (run_tests_in_docker.sh): "

DC="$(which docker-compose)"
ANTENNA_UID=${ANTENNA_UID:-"10001"}
ANTENNA_GID=${ANTENNA_GID:-"10001"}

# Use the same image we use for building docker images because it's cached.
# Otherwise this doesn't make any difference.
BASEIMAGENAME="python:3.6.8-slim"
TESTIMAGE="local/antenna_deploy_base"

# Start services in background (this is idempotent)
echo "Starting services needed by tests in the background..."
${DC} up -d localstack-s3 statsd pubsub

# If we're running a shell, then we start up a test container with . mounted
# to /app.
if [ "$1" == "--shell" ]; then
    echo "Running shell..."

    docker run \
           --rm \
           --user "${HOSTUSER}" \
           --volume "$(pwd)":/app \
           --workdir /app \
           --network antenna_default \
           --link antenna_localstack-s3_1 \
           --link antenna_statsd_1 \
           --env-file ./docker/config/local_dev.env \
           --tty \
           --interactive \
           --entrypoint="" \
           "${TESTIMAGE}" /bin/bash
    exit $?
fi

# Create a data container to hold the repo directory contents and copy the
# contents into it--reuse if possible
if [ "$(docker container ls --all | grep antenna-repo)" == "" ]; then
    echo "Creating antenna-repo container..."
    docker create \
           -v /app \
           --user "${ANTENNA_UID}" \
           --name antenna-repo \
           "${BASEIMAGENAME}" /bin/true
fi

echo "Copying contents..."

# Wipe whatever might be in there from past runs and verify files are gone
docker run \
       --user root \
       --volumes-from antenna-repo \
       --workdir /app \
       --entrypoint="" \
       "${TESTIMAGE}" sh -c "rm -rf /app/* && ls -l /app/"

# Copy the repo root into /app
docker cp . antenna-repo:/app

# Fix file permissions in data container
docker run \
       --user root \
       --volumes-from antenna-repo \
       --workdir /app \
       --entrypoint="" \
       "${TESTIMAGE}" chown -R "${ANTENNA_UID}:${ANTENNA_GID}" /app

# Run cmd in that environment and then remove the container
echo "Running tests..."
docker run \
       --rm \
       --user "${ANTENNA_UID}" \
       --volumes-from antenna-repo \
       --workdir /app \
       --network antenna_default \
       --link antenna_localstack-s3_1 \
       --link antenna_statsd_1 \
       --env-file ./docker/config/local_dev.env \
       --tty \
       --interactive \
       --entrypoint= \
       "${TESTIMAGE}" sh -c /app/docker/run_tests.sh

echo "Done!"
