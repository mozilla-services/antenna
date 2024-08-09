# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import io
import itertools
import string
from unittest.mock import ANY

from everett.manager import ConfigManager
from markus.testing import AnyTagValue
import pytest

from antenna.breakpad_resource import (
    BreakpadSubmitterResource,
    CrashReport,
    MalformedCrashReport,
)
from antenna.throttler import ACCEPT
from testlib.mini_poster import compress, multipart_encode


class FakeCrashMover:
    """Fake crash mover that raises an error when used"""

    def handle_crashreport(self, raw_crash, dumps, crash_id):
        raise NotImplementedError


EMPTY_CONFIG = ConfigManager.from_dict({})


class TestBreakpadSubmitterResourceExtract:
    def test_extract_payload(self, request_generator):
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

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        crash_report = CrashReport(
            annotations={
                "ProductName": "Firefox",
                "Version": "1.0",
            },
            dumps={"upload_file_minidump": b"abcd1234"},
            payload="multipart",
            payload_compressed="0",
            payload_size=486,
        )
        assert bsp.extract_payload(req) == crash_report

    def test_extract_payload_many_annotations(self, request_generator):
        # Test extracting with 200-ish annotations. At the time of this writing, there
        # are 165 annotations specified in CrashAnnotations.yaml. It's likely crash
        # reports send annotations not specified in that file, but 200 is probably a
        # good enough number to test with.
        data = {
            "ProductName": "Firefox",
            "Version": "1.0",
        }

        # Add another 200-ish annotations
        keys = [
            f"Annotation{char1}{char2}"
            for (char1, char2) in itertools.product(string.ascii_uppercase, "12345678")
        ]
        data.update({key: "1" for key in keys})

        assert len(data.keys()) == 210

        # Add a file
        data["upload_file_minidump"] = ("fakecrash.dump", io.BytesIO(b"abcd1234"))

        body, headers = multipart_encode(data)
        req = request_generator(
            method="POST", path="/submit", headers=headers, body=body
        )

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        crash_report = bsp.extract_payload(req)

        # Build set of expected keys--only the annotations
        expected_keys = set(data.keys())
        expected_keys -= {"upload_file_minidump"}

        assert set(crash_report.annotations.keys()) == expected_keys
        assert crash_report.dumps == {"upload_file_minidump": b"abcd1234"}

    def test_extract_payload_multipart_mixed(self, request_generator):
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

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        crash_report = CrashReport(
            annotations={
                "ProductName": "Firefox",
                "Version": "1.0",
            },
            dumps={"upload_file_minidump": b"abcd1234"},
            payload="multipart",
            payload_compressed="0",
            payload_size=486,
        )
        assert bsp.extract_payload(req) == crash_report

    def test_extract_payload_2_dumps(self, request_generator):
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

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        crash_report = CrashReport(
            annotations={
                "ProductName": "Firefox",
                "Version": "1",
            },
            dumps={
                "upload_file_minidump": b"deadbeef",
                "upload_file_minidump_flash1": b"abcd1234",
            },
            payload="multipart",
            payload_compressed="0",
            payload_size=668,
        )
        assert bsp.extract_payload(req) == crash_report

    def test_extract_payload_bad_content_type(self, request_generator):
        headers = {"Content-Type": "application/json"}
        req = request_generator(
            method="POST", path="/submit", headers=headers, body="{}"
        )

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        with pytest.raises(MalformedCrashReport, match="wrong_content_type"):
            bsp.extract_payload(req)

    def test_extract_payload_no_annotations(self, client, request_generator):
        """Verify no annotations raises error"""
        data, headers = multipart_encode({})
        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        with pytest.raises(MalformedCrashReport, match="no_annotations"):
            bsp.extract_payload(req)

    def test_extract_payload_filename_not_text(self, request_generator):
        """Verify part that has a filename is not treated as text"""
        data = (
            b"--442e931e47c9474f9bcd9b73e47aa38d\r\n"
            b'Content-Disposition: form-data; name="ProductName"\r\n'
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"Firefox\r\n"
            b"--442e931e47c9474f9bcd9b73e47aa38d\r\n"
            b'Content-Disposition: form-data; name="upload_file_minidump"; filename="dump"\r\n'
            b"\r\n"
            b"ou812\r\n"
            b"--442e931e47c9474f9bcd9b73e47aa38d--\r\n"
        )
        headers = {
            "Content-Type": "multipart/form-data; boundary=442e931e47c9474f9bcd9b73e47aa38d",
            "Content-Length": str(len(data)),
        }

        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        crash_report = CrashReport(
            annotations={
                "ProductName": "Firefox",
            },
            dumps={"upload_file_minidump": b"ou812"},
            notes=["unknown content type: upload_file_minidump text/plain"],
            payload="multipart",
            payload_compressed="0",
            payload_size=301,
        )
        assert bsp.extract_payload(req) == crash_report

    def test_extract_payload_invalid_annotation_value(self, request_generator):
        """Verify annotation that's not utf-8 is logged"""
        data = (
            b"--442e931e47c9474f9bcd9b73e47aa38d\r\n"
            b'Content-Disposition: form-data; name="Version"\r\n'
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"100"
            b"\r\n"
            b"--442e931e47c9474f9bcd9b73e47aa38d\r\n"
            b'Content-Disposition: form-data; name="ProductName"\r\n'
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"\xde\xde\xde"
            b"\r\n"
            b"--442e931e47c9474f9bcd9b73e47aa38d--\r\n"
        )
        headers = {
            "Content-Type": "multipart/form-data; boundary=442e931e47c9474f9bcd9b73e47aa38d",
            "Content-Length": str(len(data)),
        }

        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        crash_report = CrashReport(
            annotations={"Version": "100"},
            notes=[
                "extract payload text part exception: invalid text or charset: utf-8"
            ],
            payload="multipart",
            payload_size=306,
        )
        assert bsp.extract_payload(req) == crash_report

    def test_extract_payload_compressed(self, request_generator):
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

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        crash_report = CrashReport(
            annotations={
                "ProductName": "Firefox",
                "Version": "1.0",
            },
            dumps={"upload_file_minidump": b"abcd1234"},
            payload="multipart",
            payload_compressed="1",
            payload_size=486,
        )
        assert bsp.extract_payload(req) == crash_report

    def test_extract_payload_json(self, request_generator):
        data, headers = multipart_encode(
            {
                "extra": '{"ProductName":"Firefox","Version":"1.0"}',
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )
        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        crash_report = CrashReport(
            annotations={
                "ProductName": "Firefox",
                "Version": "1.0",
            },
            dumps={"upload_file_minidump": b"abcd1234"},
            payload="json",
            payload_compressed="0",
            payload_size=396,
        )
        assert bsp.extract_payload(req) == crash_report

    def test_extract_payload_invalid_json_malformed(self, request_generator):
        # If the JSON doesn't parse (invalid control character), it raises
        # a MalformedCrashReport
        data, headers = multipart_encode({"extra": '{"ProductName":"Firefox\n"}'})
        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        with pytest.raises(MalformedCrashReport, match="invalid_json"):
            bsp.extract_payload(req)

    def test_extract_payload_invalid_json_not_dict(self, request_generator):
        # If the JSON doesn't parse (invalid control character), it raises
        # a MalformedCrashReport
        data, headers = multipart_encode({"extra": '"badvalue"'})
        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        with pytest.raises(MalformedCrashReport, match="invalid_json_value"):
            bsp.extract_payload(req)

    def test_extract_payload_kvpairs_and_json(self, request_generator, metricsmock):
        # If there's a JSON blob and also kv pairs, use the annotations from "extra" and
        # log a note
        data, headers = multipart_encode(
            {
                "extra": '{"ProductName":"Firefox","Version":"1.0"}',
                # This annotation is dropped because it's not in "extra"
                "IgnoredAnnotation": "someval",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )
        req = request_generator(
            method="POST", path="/submit", headers=headers, body=data
        )

        bsp = BreakpadSubmitterResource(
            config=EMPTY_CONFIG, crashmover=FakeCrashMover()
        )
        crash_report = CrashReport(
            annotations={
                "ProductName": "Firefox",
                "Version": "1.0",
            },
            dumps={"upload_file_minidump": b"abcd1234"},
            notes=[
                "includes annotations in both json-encoded extra and formdata parts"
            ],
            payload="json",
            payload_compressed="0",
            payload_size=542,
        )
        assert bsp.extract_payload(req) == crash_report


@pytest.mark.parametrize(
    "raw_crash, expected",
    [
        ({}, {"metadata": {"collector_notes": []}}),
        (
            {"TelemetryClientId": "ou812"},
            {
                "metadata": {
                    "collector_notes": ["Removed TelemetryClientId from raw crash."]
                }
            },
        ),
        (
            {"TelemetryServerURL": "ou812"},
            {
                "metadata": {
                    "collector_notes": ["Removed TelemetryServerURL from raw crash."]
                }
            },
        ),
    ],
)
def test_cleanup_crash_report(raw_crash, expected):
    bsp = BreakpadSubmitterResource(config=EMPTY_CONFIG, crashmover=FakeCrashMover())
    bsp.cleanup_crash_report(raw_crash)
    assert raw_crash == expected


def test_get_throttle_result(client):
    raw_crash = {"ProductName": "Firefox", "ReleaseChannel": "nightly"}

    bsp = BreakpadSubmitterResource(config=EMPTY_CONFIG, crashmover=FakeCrashMover())
    assert bsp.get_throttle_result(raw_crash) == (ACCEPT, "is_nightly", 100)


class TestBreakpadSubmitterResourceIntegration:
    def test_submit_crash_report(self, client, metricsmock):
        data, headers = multipart_encode(
            {
                "ProductName": "Firefox",
                "Version": "60.0a1",
                "ReleaseChannel": "nightly",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        with metricsmock as mm:
            result = client.simulate_post("/submit", headers=headers, body=data)

        assert result.status_code == 200
        assert result.headers["Content-Type"].startswith("text/plain")
        assert result.content.startswith(b"CrashID=bp")

        crash_id = result.content.decode("utf-8").strip()[len("CrashID=bp-") :]

        crashstorage = client.get_crashmover().crashstorage
        crash_report = crashstorage.load_crash(crash_id)
        assert crash_report.crash_id == crash_id
        assert crash_report.dumps == {"upload_file_minidump": b"abcd1234"}
        assert crash_report.raw_crash == {
            "ProductName": "Firefox",
            "ReleaseChannel": "nightly",
            "Version": "60.0a1",
            "metadata": {
                "collector_notes": [],
                "dump_checksums": {
                    "upload_file_minidump": "e9cee71ab932fde863338d08be4de9dfe39ea049bdafb342ce659ec5450b69ae"
                },
                "payload": "multipart",
                "payload_compressed": "0",
                "payload_size": 632,
                "throttle_rule": "is_nightly",
                "user_agent": ANY,
            },
            "submitted_timestamp": ANY,
            "uuid": crash_id,
            "version": 2,
        }

        mm.assert_histogram("socorro.collector.breakpad_resource.crash_size", value=632)
        mm.assert_incr("socorro.collector.breakpad_resource.incoming_crash")
        mm.assert_incr(
            "socorro.collector.breakpad_resource.throttle_rule",
            tags=["rule:is_nightly", AnyTagValue("host")],
        )
        mm.assert_incr(
            "socorro.collector.breakpad_resource.throttle",
            tags=["result:accept", AnyTagValue("host")],
        )
        mm.assert_timing("socorro.collector.crashmover.crash_save.time")
        mm.assert_timing("socorro.collector.crashmover.crash_publish.time")
        mm.assert_incr("socorro.collector.crashmover.save_crash.count")
        mm.assert_timing("socorro.collector.crashmover.crash_handling.time")
        mm.assert_timing("socorro.collector.breakpad_resource.on_post.time")

    def test_existing_uuid(self, client):
        """Verify if the crash report has a uuid already, it's reused."""
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
        assert result.content.decode("utf-8") == f"CrashID=bp-{crash_id}\n"

    def test_add_user_agent_to_metadata(self, client):
        expected_user_agent = "wow"
        crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
        data, headers = multipart_encode(
            {
                "uuid": crash_id,
                "ProductName": "Firefox",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )
        headers["User-Agent"] = expected_user_agent
        client.simulate_post("/submit", headers=headers, body=data)

        crashstorage = client.get_crashmover().crashstorage
        report = crashstorage.load_crash(crash_id)

        assert report.raw_crash["metadata"]["user_agent"] == expected_user_agent
