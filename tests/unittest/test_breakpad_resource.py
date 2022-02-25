# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from collections import deque
import io

from everett.manager import ConfigManager
import pytest

from antenna.breakpad_resource import BreakpadSubmitterResource, MalformedCrashReport
from antenna.throttler import ACCEPT
from testlib.mini_poster import compress, multipart_encode


class FakeCrashMover:
    def __init__(self):
        self.crashmover_queue = deque()

    def add_crashreport(self, *args, **kwargs):
        self.crashmover_queue.append((args, kwargs))


class TestBreakpadSubmitterResource:
    empty_config = ConfigManager.from_dict({})

    def test_submit_crash_report_reply(self, client):
        data, headers = multipart_encode(
            {
                "ProductName": "Firefox",
                "Version": "60.0a1",
                "ReleaseChannel": "nightly",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)
        assert result.status_code == 200
        assert result.headers["Content-Type"].startswith("text/plain")
        assert result.content.startswith(b"CrashID=bp")

    def test_extract_payload(self, request_generator):
        crashmover = FakeCrashMover()
        data, headers = multipart_encode(
            {
                "ProductName": "Firefox",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )
        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(config=self.empty_config, crashmover=crashmover)
        expected_raw_crash = {
            "ProductName": "Firefox",
            "Version": "1.0",
            "payload": "multipart",
            "payload_compressed": "0",
        }
        expected_dumps = {"upload_file_minidump": b"abcd1234"}
        assert bsp.extract_payload(req) == (expected_raw_crash, expected_dumps)

    def test_extract_payload_multipart_mixed(self, request_generator):
        crashmover = FakeCrashMover()
        data, headers = multipart_encode(
            {
                "ProductName": "Firefox",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            },
            mimetype="multipart/mixed",
        )
        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(config=self.empty_config, crashmover=crashmover)
        expected_raw_crash = {
            "ProductName": "Firefox",
            "Version": "1.0",
            "payload": "multipart",
            "payload_compressed": "0",
        }
        expected_dumps = {"upload_file_minidump": b"abcd1234"}
        assert bsp.extract_payload(req) == (expected_raw_crash, expected_dumps)

    def test_extract_payload_2_dumps(self, request_generator):
        crashmover = FakeCrashMover()
        data, headers = multipart_encode(
            {
                "ProductName": "Firefox",
                "Version": "1",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"deadbeef")),
                "upload_file_minidump_flash1": (
                    "fakecrash2.dump",
                    io.BytesIO(b"abcd1234"),
                ),
            }
        )

        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(config=self.empty_config, crashmover=crashmover)
        expected_raw_crash = {
            "ProductName": "Firefox",
            "Version": "1",
            "payload": "multipart",
            "payload_compressed": "0",
        }
        expected_dumps = {
            "upload_file_minidump": b"deadbeef",
            "upload_file_minidump_flash1": b"abcd1234",
        }
        assert bsp.extract_payload(req) == (expected_raw_crash, expected_dumps)

    def test_extract_payload_bad_content_type(self, request_generator):
        crashmover = FakeCrashMover()
        headers = {"Content-Type": "application/json"}
        req = request_generator(
            method="POST", path="/submit", headers=headers, body="{}"
        )

        bsp = BreakpadSubmitterResource(config=self.empty_config, crashmover=crashmover)
        with pytest.raises(MalformedCrashReport, match="wrong_content_type"):
            bsp.extract_payload(req)

    def test_extract_payload_compressed(self, request_generator):
        crashmover = FakeCrashMover()
        data, headers = multipart_encode(
            {
                "ProductName": "Firefox",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        data = compress(data)
        headers["Content-Encoding"] = "gzip"

        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(config=self.empty_config, crashmover=crashmover)
        expected_raw_crash = {
            "ProductName": "Firefox",
            "Version": "1.0",
            "payload": "multipart",
            "payload_compressed": "1",
        }
        expected_dumps = {"upload_file_minidump": b"abcd1234"}
        assert bsp.extract_payload(req) == (expected_raw_crash, expected_dumps)

    def test_extract_payload_json(self, request_generator):
        crashmover = FakeCrashMover()
        data, headers = multipart_encode(
            {
                "extra": '{"ProductName":"Firefox","Version":"1.0"}',
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )
        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(config=self.empty_config, crashmover=crashmover)
        expected_raw_crash = {
            "ProductName": "Firefox",
            "Version": "1.0",
            "payload": "json",
            "payload_compressed": "0",
        }
        expected_dumps = {"upload_file_minidump": b"abcd1234"}
        assert bsp.extract_payload(req) == (expected_raw_crash, expected_dumps)

    def test_extract_payload_bad_json_malformed(self, request_generator):
        crashmover = FakeCrashMover()

        # If the JSON doesn't parse (invalid control character), it raises
        # a MalformedCrashReport
        data, headers = multipart_encode({"extra": '{"ProductName":"Firefox\n"}'})
        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(config=self.empty_config, crashmover=crashmover)
        with pytest.raises(MalformedCrashReport, match="bad_json"):
            bsp.extract_payload(req)

    def test_extract_payload_bad_json_not_dict(self, request_generator):
        crashmover = FakeCrashMover()

        # If the JSON doesn't parse (invalid control character), it raises
        # a MalformedCrashReport
        data, headers = multipart_encode({"extra": '"badvalue"'})
        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(config=self.empty_config, crashmover=crashmover)
        with pytest.raises(MalformedCrashReport, match="bad_json"):
            bsp.extract_payload(req)

    def text_extract_payload_kvpairs_and_json(self, request_generator, metricsmock):
        crashmover = FakeCrashMover()

        # If there's a JSON blob and also kv pairs, then that's a malformed
        # crash
        data, headers = multipart_encode(
            {
                "extra": '{"ProductName":"Firefox","Version":"1.0"}',
                "BadKey": "BadValue",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )
        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(config=self.empty_config, crashmover=crashmover)
        with metricsmock as metrics:
            result = bsp.extract_payload(req)
            assert result == ({}, {})
            assert metrics.has_record(stat="malformed", tags=["reason:has_json_and_kv"])

    def test_existing_uuid(self, client):
        crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
        data, headers = multipart_encode(
            {
                "uuid": crash_id,
                "ProductName": "Firefox",
                "Version": "60.0a1",
                "ReleaseChannel": "nightly",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)
        assert result.status_code == 200

        # Extract the uuid from the response content and verify that it's the
        # crash id we sent
        assert result.content.decode("utf-8") == "CrashID=bp-%s\n" % crash_id

    @pytest.mark.parametrize(
        "raw_crash, expected",
        [
            ({}, {"collector_notes": []}),
            (
                {"TelemetryClientId": "ou812"},
                {"collector_notes": ["Removed TelemetryClientId from raw crash."]},
            ),
            (
                {"TelemetryServerURL": "ou812"},
                {"collector_notes": ["Removed TelemetryServerURL from raw crash."]},
            ),
        ],
    )
    def test_cleanup_crash_report(self, client, raw_crash, expected):
        bsp = BreakpadSubmitterResource(
            config=self.empty_config,
            crashmover=client.get_crashmover(),
        )
        bsp.cleanup_crash_report(raw_crash)
        assert raw_crash == expected

    def test_get_throttle_result(self):
        crashmover = FakeCrashMover()
        raw_crash = {"ProductName": "Firefox", "ReleaseChannel": "nightly"}

        bsp = BreakpadSubmitterResource(config=self.empty_config, crashmover=crashmover)
        assert bsp.get_throttle_result(raw_crash) == (ACCEPT, "is_nightly", 100)

    def test_queuing(self, client):
        # Rebuild the app so the client only saves one crash at a time to s3
        client.rebuild_app({"CRASHMOVER_CONCURRENT_SAVES": "1"})

        def check_health(crashmover_pool_size, crashmover_queue_size):
            crashmover = client.app.crashmover
            assert len(crashmover.crashmover_queue) == crashmover_queue_size
            assert len(crashmover.crashmover_pool) == crashmover_pool_size

        data, headers = multipart_encode(
            {
                "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
                "ProductName": "Firefox",
                "Version": "60.0a1",
                "ReleaseChannel": "nightly",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        # Verify initial conditions are correct--no active coroutines and
        # nothing in the queue
        check_health(crashmover_pool_size=0, crashmover_queue_size=0)

        # Submit a crash
        client.simulate_post("/submit", headers=headers, body=data)
        # Now there's one coroutine active and one item in the queue
        check_health(crashmover_pool_size=1, crashmover_queue_size=1)

        # Submit another crash
        client.simulate_post("/submit", headers=headers, body=data)
        # The coroutine hasn't run yet (we haven't called .join), so there's
        # one coroutine and two queued crashes to be saved
        check_health(crashmover_pool_size=2, crashmover_queue_size=2)

        # Now join the app and let the coroutines run and make sure the queue clears
        client.join_app()
        # No more coroutines and no more queue
        check_health(crashmover_pool_size=0, crashmover_queue_size=0)
