#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

gunicorn \
    --reload \
    --bind=0.0.0.0:8000 \
    --workers=1 \
    --worker-connections=1 \
    --worker-class=gevent \
    antenna.wsgi:application \
    --log-file -
