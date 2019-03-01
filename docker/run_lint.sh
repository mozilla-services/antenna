#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Runs linting.

# This should be called from inside a container

set -e

echo ">>> flake8"
flake8 --statistics antenna tests/unittest/

echo ">>> bandit"
bandit -r antenna/
