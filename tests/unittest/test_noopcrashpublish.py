# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from everett.manager import ConfigManager

from antenna.crashmover import CrashReport
from antenna.ext.crashpublish_base import NoOpCrashPublish


EMPTY_CONFIG = ConfigManager.from_dict({})


def test_publish():
    crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
    crash_report = CrashReport(
        crash_id=crash_id,
        raw_crash={
            "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
            "ProductName": "Test",
            "Version": "1.0",
        },
        dumps={"upload_file_minidump": b"abcd1234"},
    )
    noop = NoOpCrashPublish(config=EMPTY_CONFIG)
    noop.publish_crash(crash_report)

    assert noop.published_things == [{"crash_id": crash_id}]
