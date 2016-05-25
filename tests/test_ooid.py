# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# This is based on socorrolib's socorrolib/unittest/lib/testOoid.py module
# with a heavy flake8/pytest pass.

import uuid
from datetime import datetime
from unittest import TestCase

from antenna.lib.datetimeutil import utc_now, UTC
from antenna.lib.ooid import (
    create_new_ooid,
    date_from_ooid,
    date_and_depth_from_ooid,
    depth_from_ooid,
    DEFAULT_DEPTH,
    uuid_to_ooid,
)


class Test_ooid(TestCase):
    def setUp(self):
        self.base_date = datetime(2008, 12, 25, tzinfo=UTC)
        self.rawuuids = []
        self.yyyyoids = []
        self.dyyoids = []
        self.depths = [4, 4, 3, 3, 3, 2, 2, 2, 1, 1]
        self.badooid0 = "%s%s" % (str(uuid.uuid4())[:-8], 'ffeea1b2')
        self.badooid1 = "%s%s" % (str(uuid.uuid4())[:-8], 'f3eea1b2')

        for i in range(10):
            self.rawuuids.append(str(uuid.uuid4()))
        assert len(self.depths) == len(self.rawuuids)

        for i in self.rawuuids:
            self.yyyyoids.append("%s%4d%02d%02d" % (
                i[:-8],
                self.base_date.year,
                self.base_date.month,
                self.base_date.day
            ))

        for i in range(len(self.rawuuids)):
            self.dyyoids.append("%s%d%02d%02d%02d" % (
                self.rawuuids[i][:-7],
                self.depths[i],
                self.base_date.year % 100,
                self.base_date.month,
                self.base_date.day
            ))

        today = utc_now()
        self.nowstamp = datetime(
            today.year, today.month, today.day, tzinfo=UTC
        )
        self.xmas05 = datetime(2005, 12, 25, tzinfo=UTC)

    def test_create_new_ooid(self):
        ooid = create_new_ooid()
        assert date_from_ooid(ooid) == self.nowstamp
        assert depth_from_ooid(ooid) == DEFAULT_DEPTH

        ooid = create_new_ooid(timestamp=self.xmas05)
        assert date_from_ooid(ooid) == self.xmas05
        assert depth_from_ooid(ooid) == DEFAULT_DEPTH

        for d in range(1, 5):
            ooid0 = create_new_ooid(depth=d)
            ooid1 = create_new_ooid(timestamp=self.xmas05, depth=d)

            ndepth0 = depth_from_ooid(ooid0)
            ndepth1 = depth_from_ooid(ooid1)

            assert date_from_ooid(ooid0) == self.nowstamp
            assert date_from_ooid(ooid1) == self.xmas05
            assert ndepth0 == ndepth1
            assert ndepth0 == d

        assert depth_from_ooid(self.badooid0) is None
        assert depth_from_ooid(self.badooid1) is None

    def test_uuid_to_ooid(self):
        for i in range(len(self.rawuuids)):
            u = self.rawuuids[i]

            o0 = uuid_to_ooid(u)
            assert date_and_depth_from_ooid(o0) == (
                self.nowstamp, DEFAULT_DEPTH
            )

            o1 = uuid_to_ooid(u, timestamp=self.base_date)
            assert date_and_depth_from_ooid(o1) == (
                self.base_date, DEFAULT_DEPTH
            )

            o2 = uuid_to_ooid(u, depth=self.depths[i])
            assert date_and_depth_from_ooid(o2) == (
                self.nowstamp, self.depths[i]
            )

            o3 = uuid_to_ooid(
                u, depth=self.depths[i], timestamp=self.xmas05
            )
            assert date_and_depth_from_ooid(o3) == (
                self.xmas05, self.depths[i]
            )

    def test_date_from_ooid(self):
        for ooid in self.yyyyoids:
            assert date_from_ooid(ooid) == self.base_date
            assert depth_from_ooid(ooid) == 4

        assert date_from_ooid(self.badooid0) is None
        assert date_from_ooid(self.badooid1) is None

    def test_date_and_depth_from_ooid(self):
        for i in range(len(self.dyyoids)):
            date, depth = date_and_depth_from_ooid(self.dyyoids[i])
            assert depth == self.depths[i]
            assert date == self.base_date

        assert date_and_depth_from_ooid(self.badooid0) == (None, None)
        assert date_and_depth_from_ooid(self.badooid1) == (None, None)
