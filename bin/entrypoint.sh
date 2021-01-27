#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Usage: bin/entrypoint.sh SERVICE

set -euo pipefail

# Entrypoint for Antenna image

if [ -z "$*" ]; then
    echo "usage: entrypoint.sh SERVICE"
    echo ""
    echo "Services:"
    grep -E '^[a-zA-Z0-9_-]+).*?## .*$$' bin/entrypoint.sh \
        | grep -v grep \
        | sed -n 's/^\(.*\)) \(.*\)##\(.*\)/* \1:\3/p'
    exit 1
fi

SERVICE=$1
shift

case ${SERVICE} in
web)  ## Run web service
    /app/bin/run_web.sh "$@"
    ;;
shell)  ## Open a shell or run something else
    if [ -z "$*" ]; then
        bash
    else
        "$@"
    fi
    ;;
*)
    echo "Unknown service ${SERVICE}"
    exit 1
esac
