#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Builds docs in the docs/ directory.

# Clean the docs first
make -C docs/ clean

# Build the HTML docs
make -C docs/ html
