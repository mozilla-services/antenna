# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


from datetime import datetime
from freezegun import freeze_time
import pytest

from antenna.util import (
    create_crash_id,
    get_date_from_crash_id,
    de_null,
)


@pytest.mark.parametrize('data,expected', [
    # no nulls--just making sure things are good
    ('abc', 'abc'),
    (b'abc', b'abc'),
    (123, 123),

    # has nulls
    ('abc\0', 'abc'),
    ('ab\0c\0', 'abc'),
    (b'abc\0', b'abc'),
    (b'a\0bc\0', b'abc'),
])
def test_de_null(data, expected):
    assert de_null(data) == expected


@freeze_time('2011-09-06 00:00:00', tz_offset=0)
def test_crash_id():
    """Tests creating crash ids"""
    crash_id = create_crash_id()

    assert get_date_from_crash_id(crash_id) == '20110906'
    assert get_date_from_crash_id(crash_id, as_datetime=True).strftime('%Y%m%d') == '20110906'


def test_crash_id_with_date():
    """Tests creating a crash id with a timestamp"""
    crash_id = create_crash_id(datetime(2016, 10, 4))

    assert get_date_from_crash_id(crash_id) == '20161004'
