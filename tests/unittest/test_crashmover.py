# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import io

from everett.manager import ConfigManager

from antenna.ext.crashpublish_base import CrashPublishBase
from antenna.ext.crashstorage_base import CrashStorageBase


class BadCrashStorage(CrashStorageBase):
    def save_crash(self, crash_report):
        raise Exception


class BadCrashPublish(CrashPublishBase):
    def publish_crash(self, crash_id):
        raise Exception


class TestCrashMover:
    empty_config = ConfigManager.from_dict({})

    def test_retry_storage(self, client, caplog):
        crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
        raw_crash = {
            "uuid": crash_id,
            "ProductName": "Firefox",
            "Version": "60.0a1",
            "ReleaseChannel": "nightly",
        }
        dumps = {
            "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
        }

        client.rebuild_app(
            {
                "CRASHMOVER_CRASHSTORAGE_CLASS": (
                    f"{BadCrashStorage.__module__}.{BadCrashStorage.__name__}"
                )
            }
        )

        # Add crash report to queue
        succeeded = client.get_crashmover().handle_crashreport(
            raw_crash=raw_crash,
            dumps=dumps,
            crash_id=crash_id,
        )
        assert not succeeded

        # We're using BadCrashStorage so the crashmover should retry 20
        # times logging a message each time and then give up
        records = [
            rec[2] for rec in caplog.record_tuples if rec[0] == "antenna.crashmover"
        ]
        assert records == [
            *(
                f"CrashMover.crashmover_save: exception , retry attempt {i}"
                for i in range(20)
            ),
            f"{crash_id}: too many errors trying to save; dropped",
        ]

    def test_retry_publish(self, client, caplog):
        crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
        raw_crash = {
            "uuid": crash_id,
            "ProductName": "Firefox",
            "Version": "60.0a1",
            "ReleaseChannel": "nightly",
        }
        dumps = {
            "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
        }

        client.rebuild_app(
            {
                "CRASHMOVER_CRASHPUBLISH_CLASS": (
                    f"{BadCrashPublish.__module__}.{BadCrashPublish.__name__}"
                )
            }
        )

        # Add crash report to queue
        succeeded = client.get_crashmover().handle_crashreport(
            raw_crash=raw_crash,
            dumps=dumps,
            crash_id=crash_id,
        )
        assert succeeded

        # We're using BadCrashStorage so the crashmover should retry 20
        # times logging a message each time and then give up
        records = [
            rec[2] for rec in caplog.record_tuples if rec[0] == "antenna.crashmover"
        ]

        assert records == [
            f"{crash_id} saved",
            *(
                f"CrashMover.crashmover_publish: exception , retry attempt {i}"
                for i in range(5)
            ),
            f"{crash_id}: too many errors trying to publish; dropped",
        ]
