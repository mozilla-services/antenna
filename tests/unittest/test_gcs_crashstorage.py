# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import io
import os
from unittest.mock import Mock, patch, ANY

import pytest
from google.cloud.exceptions import NotFound, Unauthorized

from antenna.ext.crashstorage_base import CrashIDNotFound
from testlib.mini_poster import multipart_encode


@pytest.fixture(autouse=True)
def mock_generate_test_filepath():
    with patch("antenna.ext.gcs.crashstorage.generate_test_filepath") as gtfp:
        gtfp.return_value = "test/testwrite.txt"
        yield


class TestGcsCrashStorageIntegration:
    logging_names = ["antenna"]

    def test_crash_storage(self, client, gcs_helper):
        bucket_name = os.environ["CRASHMOVER_CRASHSTORAGE_BUCKET_NAME"]
        gcs_bucket = gcs_helper.bucket(bucket_name)

        crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
        data, headers = multipart_encode(
            {
                "uuid": crash_id,
                "ProductName": "Firefox",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app(
            {
                "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.gcs.crashstorage.GcsCrashStorage",
                "CRASHMOVER_CRASHSTORAGE_BUCKET_NAME": gcs_bucket.name,
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)

        # Verify the collector returns a 200 status code and the crash id
        # we fed it.
        assert result.status_code == 200
        assert result.content == f"CrashID=bp-{crash_id}\n".encode("utf-8")

        # Assert we uploaded files to gcs
        blobs = sorted(gcs_bucket.list_blobs(), key=lambda b: b.name)

        blob_names = [b.name for b in blobs]
        assert blob_names == [
            "test/testwrite.txt",
            f"v1/dump/{crash_id}",
            f"v1/dump_names/{crash_id}",
            f"v1/raw_crash/20160918/{crash_id}",
        ]

        blob_contents = [
            b.download_as_bytes()
            for b in blobs
            # ignore the contents of the raw crash
            if not b.name.startswith("v1/raw_crash")
        ]
        assert blob_contents == [
            b"test",
            b"abcd1234",
            b'["upload_file_minidump"]',
        ]

    def test_missing_bucket_halts_startup(self, client, gcs_helper):
        bucket_name = "missingbucket"

        # Ensure bucket is actually missing
        with pytest.raises(NotFound):
            gcs_helper.get_bucket(bucket_name)

        with pytest.raises(NotFound) as excinfo:
            # Rebuild the app the test client is using with relevant
            # configuration. This calls .verify_write_to_bucket() which fails.
            client.rebuild_app(
                {
                    "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.gcs.crashstorage.GcsCrashStorage",
                    "CRASHMOVER_CRASHSTORAGE_BUCKET_NAME": bucket_name,
                }
            )

        assert f"b/{bucket_name}" in excinfo.value.args[0]

    @patch("google.cloud.storage.Client")
    def test_write_error(self, MockStorageClient, client):
        mock_client = MockStorageClient.return_value
        bucket = mock_client.get_bucket.return_value
        good_blob = Mock()
        bad_blob = Mock()
        bad_blob.upload_from_string.side_effect = Unauthorized("not authorized")

        def get_blob(path):
            if path == "test/testwrite.txt":
                return good_blob
            return bad_blob

        bucket.blob = get_blob

        crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
        data, headers = multipart_encode(
            {
                "uuid": crash_id,
                "ProductName": "Firefox",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app(
            {
                "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.gcs.crashstorage.GcsCrashStorage",
                "CRASHMOVER_CRASHSTORAGE_BUCKET_NAME": "fakebucket",
                "CRASHMOVER_MAX_ATTEMPTS": "1",
                "CRASHMOVER_RETRY_SLEEP_SECONDS": "0",
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)

        # Verify the collector returns a 500 status code and no crash id.
        assert result.status_code == 500
        assert result.content == b""

    def test_load_file(self, client, gcs_helper):
        crash_id = "de1bb258-cbbf-4589-a673-34f800160918"
        data, headers = multipart_encode(
            {
                "uuid": crash_id,
                "ProductName": "Firefox",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app(
            {
                "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.gcs.crashstorage.GcsCrashStorage",
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)

        # Verify the collector returns a 200 status code and the crash id
        # we fed it.
        assert result.status_code == 200

        gcs_crashstorage = client.get_crashmover().crashstorage
        report = gcs_crashstorage.load_crash(crash_id)

        assert report.crash_id == crash_id
        assert report.dumps == {"upload_file_minidump": b"abcd1234"}
        assert report.raw_crash == {
            "ProductName": "Firefox",
            "Version": "1.0",
            "metadata": {
                "collector_notes": [],
                "dump_checksums": {
                    "upload_file_minidump": "e9cee71ab932fde863338d08be4de9dfe39ea049bdafb342ce659ec5450b69ae"
                },
                "payload": "multipart",
                "payload_compressed": "0",
                "payload_size": 648,
                "throttle_rule": "accept_everything",
            },
            "submitted_timestamp": ANY,
            "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
            "version": 2,
        }

    def test_load_file_no_data(self, client, gcs_helper):
        crash_id = "de1bb258-cbbf-4589-a673-34f800160918"

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app(
            {
                "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.gcs.crashstorage.GcsCrashStorage",
            }
        )

        gcs_crashstorage = client.get_crashmover().crashstorage
        with pytest.raises(CrashIDNotFound):
            gcs_crashstorage.load_crash(crash_id)
