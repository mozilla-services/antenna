#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Runs the webapp.

set -euxo pipefail

PORT=${PORT:-"8000"}
GUNICORN_WORKERS=${GUNICORN_WORKERS:-"1"}
GUNICORN_WORKER_CLASS=${GUNICORN_WORKER_CLASS:-"sync"}
GUNICORN_MAX_REQUESTS=${GUNICORN_MAX_REQUESTS:-"0"}
GUNICORN_MAX_REQUESTS_JITTER=${GUNICORN_MAX_REQUESTS_JITTER:-"0"}
CMD_PREFIX=${CMD_PREFIX:-""}
STATSD_HOST=${STATSD_HOST:-localhost}
STATSD_PORT=${STATSD_PORT:-8125}
HOSTNAME=${HOSTNAME:-$(hostname)}

${CMD_PREFIX} gunicorn \
    --workers="${GUNICORN_WORKERS}" \
    --worker-class="${GUNICORN_WORKER_CLASS}" \
    --max-requests="${GUNICORN_MAX_REQUESTS}" \
    --max-requests-jitter="${GUNICORN_MAX_REQUESTS_JITTER}" \
    --statsd-host=${STATSD_HOST}:${STATSD_PORT} \
    --statsd-prefix=socorro.collector \
    --dogstatsd-tags=host:$HOSTNAME \
    --log-file=- \
    --error-logfile=- \
    --access-logfile=- \
    --bind 0.0.0.0:"${PORT}" \
    antenna.wsgi:application
