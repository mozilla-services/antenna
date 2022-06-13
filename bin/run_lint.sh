#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Usage: bin/run_lint.sh [--fix]
#
# Runs linting and code fixing.
#
# This should be called from inside a container.

set -euo pipefail

BLACKARGS=("--line-length=88" "--target-version=py37" antenna bin testlib tests systemtest)

if [[ "${1:-}" == "--fix" ]]; then
    echo ">>> black fix"
    black "${BLACKARGS[@]}"

else
    echo ">>> flake8"
    flake8 --statistics antenna tests/unittest/ systemtest/

    echo ">>> black"
    black --check "${BLACKARGS[@]}"

    echo ">>> bandit"
    bandit -r antenna/

    echo ">>> license check"
    python bin/license_check.py .
fi
