# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import io
from unittest.mock import call, Mock, patch

import pytest
from google.cloud.exceptions import NotFound, Unauthorized

from testlib.mini_poster import multipart_encode


@pytest.fixture(autouse=True)
def mock_generate_test_filepath():
    with patch("antenna.ext.gcs.crashstorage.generate_test_filepath") as gtfp:
        gtfp.return_value = "test/testwrite.txt"
        yield


class TestGcsCrashStorageIntegration:
    logging_names = ["antenna"]

    @pytest.mark.parametrize("bucket_name", ["fakebucket", "fakebucket.with.periods"])
    @patch("google.cloud.storage.Client")
    def test_crash_storage(self, MockStorageClient, client, bucket_name):
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
                "CRASHMOVER_CRASHSTORAGE_BUCKET_NAME": bucket_name,
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)

        # Verify the collector returns a 200 status code and the crash id
        # we fed it.
        assert result.status_code == 200
        assert result.content == f"CrashID=bp-{crash_id}\n".encode("utf-8")

        # Assert we uploaded files to gcs
        mock_client = MockStorageClient.return_value
        bucket = mock_client.get_bucket.return_value
        blob = bucket.blob.return_value
        upload_calls = blob.upload_from_string.mock_calls
        blob_calls = [c for c in bucket.blob.mock_calls if c not in upload_calls]
        bucket_calls = [
            c
            for c in mock_client.get_bucket.mock_calls
            if c not in blob_calls and c not in upload_calls
        ]

        assert bucket_calls == [call(bucket_name)] * 4
        assert blob_calls == [
            call("test/testwrite.txt"),
            call(f"v1/dump_names/{crash_id}"),
            call(f"v1/dump/{crash_id}"),
            call(f"v1/raw_crash/20160918/{crash_id}"),
        ]
        # upload_contents = [c.args[0].read() for c in upload_calls]
        # ignore the contents of the last upload call
        assert upload_calls[:-1] == [
            call(b"test"),
            call(b'["upload_file_minidump"]'),
            call(b"abcd1234"),
        ]

    @patch("google.cloud.storage.Client")
    def test_missing_bucket_halts_startup(self, MockStorageClient, client):
        mock_client = MockStorageClient.return_value
        mock_client.get_bucket.side_effect = NotFound("bucket not found")

        with pytest.raises(NotFound) as excinfo:
            # Rebuild the app the test client is using with relevant
            # configuration. This calls .verify_write_to_bucket() which fails.
            client.rebuild_app(
                {
                    "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.gcs.crashstorage.GcsCrashStorage",
                    "CRASHMOVER_CRASHSTORAGE_BUCKET_NAME": "fakebucket",
                }
            )

        assert "404 bucket not found" == str(excinfo.value)

        mock_client.get_bucket.assert_called_once_with("fakebucket")

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
