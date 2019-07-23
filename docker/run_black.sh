#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Runs black which formats Python code.
#
# This should be called from inside a container.

set -e
black --line-length=88 --target-version py36 testlib tests $@
