# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# This is based on socorrolib's socorrolib/unittest/lib/test_datetimeutil.py.

from antenna import datetimeutil


UTC = datetimeutil.UTC


def test_utc_now():
    res = datetimeutil.utc_now()
    assert res.strftime('%Z') == 'UTC'
    assert res.strftime('%z') == '+0000'
    assert res.tzinfo
