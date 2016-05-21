# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

ACCEPT = 0   # save and process
DEFER = 1    # save but don't process
DISCARD = 2  # tell client to go away and not come back
IGNORE = 3   # ignore submission entirely


class Throttler:
    def __init__(self, config):
        pass

    def throttle(self, raw_crash):
        # FIXME: Implement
        return ACCEPT, 100
