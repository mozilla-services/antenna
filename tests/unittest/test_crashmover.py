# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import io

from everett.manager import ConfigManager

from antenna.ext.crashpublish_base import CrashPublishBase
from antenna.ext.crashstorage_base import CrashStorageBase


class BadCrashStorage(CrashStorageBase):
    def save_dumps(self, crash_id, dumps):
        raise Exception

    def save_raw_crash(self, crash_id, raw_crash):
        raise Exception


class BadCrashPublish(CrashPublishBase):
    def publish_crash(self, crash_id):
        raise Exception


class TestCrashMover:
    empty_config = ConfigManager.from_dict({})

    def test_queuing(self, client):
        def check_health(crashmover_pool_size, crashmover_queue_size):
            crashmover = client.get_crashmover()
            assert len(crashmover.crashmover_queue) == crashmover_queue_size
            assert len(crashmover.crashmover_pool) == crashmover_pool_size

        # Rebuild the app so the client only saves one crash at a time to s3
        client.rebuild_app({"CRASHMOVER_CONCURRENT_SAVES": "1"})

        crashmover = client.get_crashmover()

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

        # Verify initial conditions are correct--no active coroutines and
        # nothing in the queue
        check_health(crashmover_pool_size=0, crashmover_queue_size=0)

        # Submit a crash
        crashmover.add_crashreport(
            raw_crash=raw_crash,
            dumps=dumps,
            crash_id=crash_id,
        )

        # Now there's one coroutine active and one item in the queue
        check_health(crashmover_pool_size=1, crashmover_queue_size=1)

        # Submit another crash
        crashmover.add_crashreport(
            raw_crash=raw_crash,
            dumps=dumps,
            crash_id=crash_id,
        )

        # The coroutine hasn't run yet (we haven't called .join), so there's
        # one coroutine and two queued crashes to be saved
        check_health(crashmover_pool_size=2, crashmover_queue_size=2)

        # Now join the app and let the coroutines run and make sure the queue clears
        client.join_app()

        # No more coroutines and no more queue
        check_health(crashmover_pool_size=0, crashmover_queue_size=0)

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
        client.get_crashmover().add_crashreport(
            raw_crash=raw_crash,
            dumps=dumps,
            crash_id=crash_id,
        )

        # The storage is bad, so this should raise errors and then log something
        client.join_app()

        # We're using BadCrashStorage so the crashmover should retry 20
        # times logging a message each time and then give up
        records = [
            rec[2] for rec in caplog.record_tuples if rec[0] == "antenna.crashmover"
        ]
        assert records == [
            f"Exception when processing queue ({crash_id}), state: save; error 1/20",
            f"Exception when processing queue ({crash_id}), state: save; error 2/20",
            f"Exception when processing queue ({crash_id}), state: save; error 3/20",
            f"Exception when processing queue ({crash_id}), state: save; error 4/20",
            f"Exception when processing queue ({crash_id}), state: save; error 5/20",
            f"Exception when processing queue ({crash_id}), state: save; error 6/20",
            f"Exception when processing queue ({crash_id}), state: save; error 7/20",
            f"Exception when processing queue ({crash_id}), state: save; error 8/20",
            f"Exception when processing queue ({crash_id}), state: save; error 9/20",
            f"Exception when processing queue ({crash_id}), state: save; error 10/20",
            f"Exception when processing queue ({crash_id}), state: save; error 11/20",
            f"Exception when processing queue ({crash_id}), state: save; error 12/20",
            f"Exception when processing queue ({crash_id}), state: save; error 13/20",
            f"Exception when processing queue ({crash_id}), state: save; error 14/20",
            f"Exception when processing queue ({crash_id}), state: save; error 15/20",
            f"Exception when processing queue ({crash_id}), state: save; error 16/20",
            f"Exception when processing queue ({crash_id}), state: save; error 17/20",
            f"Exception when processing queue ({crash_id}), state: save; error 18/20",
            f"Exception when processing queue ({crash_id}), state: save; error 19/20",
            f"Exception when processing queue ({crash_id}), state: save; error 20/20",
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
        client.get_crashmover().add_crashreport(
            raw_crash=raw_crash,
            dumps=dumps,
            crash_id=crash_id,
        )

        # The publish is bad, so this should raise errors and then log something
        client.join_app()

        # We're using BadCrashStorage so the crashmover should retry 20
        # times logging a message each time and then give up
        records = [
            rec[2] for rec in caplog.record_tuples if rec[0] == "antenna.crashmover"
        ]

        assert records == [
            f"{crash_id} saved",
            f"Exception when processing queue ({crash_id}), state: publish; error 1/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 2/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 3/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 4/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 5/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 6/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 7/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 8/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 9/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 10/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 11/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 12/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 13/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 14/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 15/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 16/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 17/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 18/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 19/20",
            f"Exception when processing queue ({crash_id}), state: publish; error 20/20",
            f"{crash_id}: too many errors trying to publish; dropped",
        ]
