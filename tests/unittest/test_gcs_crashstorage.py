# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import io
from unittest.mock import Mock, patch

import pytest
from google.cloud.exceptions import Unauthorized

from testlib.mini_poster import multipart_encode


@pytest.fixture(autouse=True)
def mock_generate_test_filepath():
    with patch("antenna.ext.gcs.crashstorage.generate_test_filepath") as gtfp:
        gtfp.return_value = "test/testwrite.txt"
        yield


class TestGcsCrashStorageIntegration:
    logging_names = ["antenna"]

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
