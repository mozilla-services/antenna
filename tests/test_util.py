# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

from antenna.util import de_null


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
