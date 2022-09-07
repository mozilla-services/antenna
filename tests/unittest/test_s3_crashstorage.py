# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import io
import logging
from unittest.mock import patch

import botocore
import pytest

from testlib.mini_poster import multipart_encode


@pytest.fixture
def mock_generate_test_filepath():
    with patch("antenna.ext.s3.connection.generate_test_filepath") as gtfp:
        gtfp.return_value = "test/testwrite.txt"
        yield


class TestS3CrashStorageIntegration:
    logging_names = ["antenna"]

    def test_crash_storage(self, client, s3mock, mock_generate_test_filepath):
        # .verify_write_to_bucket() writes to the bucket to verify Antenna can
        # write to it and the configuration is correct
        s3mock.add_step(
            method="PUT",
            url="http://fakes3:4569/fakebucket/test/testwrite.txt",
            body=b"test",
            resp=s3mock.fake_response(status_code=200),
        )

        # # We want to verify these files are saved in this specific order.
        s3mock.add_step(
            method="PUT",
            url=(
                "http://fakes3:4569/fakebucket/v1/dump_names/"
                + "de1bb258-cbbf-4589-a673-34f800160918"
            ),
            body=b'["upload_file_minidump"]',
            resp=s3mock.fake_response(status_code=200),
        )
        s3mock.add_step(
            method="PUT",
            url="http://fakes3:4569/fakebucket/v1/dump/de1bb258-cbbf-4589-a673-34f800160918",
            body=b"abcd1234",
            resp=s3mock.fake_response(status_code=200),
        )
        s3mock.add_step(
            method="PUT",
            url=(
                "http://fakes3:4569/fakebucket/v1/raw_crash/20160918/"
                + "de1bb258-cbbf-4589-a673-34f800160918"
            ),
            # Not going to compare the body here because it's just the raw crash
            resp=s3mock.fake_response(status_code=200),
        )
        data, headers = multipart_encode(
            {
                "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
                "ProductName": "Firefox",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app(
            {
                "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.s3.crashstorage.S3CrashStorage",
                "CRASHMOVER_CRASHSTORAGE_ENDPOINT_URL": "http://fakes3:4569",
                "CRASHMOVER_CRASHSTORAGE_ACCESS_KEY": "fakekey",
                "CRASHMOVER_CRASHSTORAGE_SECRET_ACCESS_KEY": "fakesecretkey",
                "CRASHMOVER_CRASHSTORAGE_BUCKET_NAME": "fakebucket",
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)
        client.join_app()

        # Verify the collector returns a 200 status code and the crash id
        # we fed it.
        assert result.status_code == 200
        assert result.content == b"CrashID=bp-de1bb258-cbbf-4589-a673-34f800160918\n"

        # Assert we did the entire s3 conversation
        assert s3mock.remaining_conversation() == []

    def test_region_and_bucket_with_periods(
        self, client, s3mock, mock_generate_test_filepath
    ):
        # .verify_write_to_bucket() writes to the bucket to verify Antenna can
        # write to it and the configuration is correct
        s3mock.add_step(
            method="PUT",
            url="http://fakes3:4569/fakebucket.with.periods/test/testwrite.txt",
            body=b"test",
            resp=s3mock.fake_response(status_code=200),
        )

        # We want to verify these files are saved in this specific order.
        s3mock.add_step(
            method="PUT",
            url=(
                "http://fakes3:4569/fakebucket.with.periods/v1/dump_names/"
                "de1bb258-cbbf-4589-a673-34f800160918"
            ),
            body=b'["upload_file_minidump"]',
            resp=s3mock.fake_response(status_code=200),
        )
        s3mock.add_step(
            method="PUT",
            url=(
                "http://fakes3:4569/fakebucket.with.periods/v1/dump/"
                "de1bb258-cbbf-4589-a673-34f800160918"
            ),
            body=b"abcd1234",
            resp=s3mock.fake_response(status_code=200),
        )
        s3mock.add_step(
            method="PUT",
            url=(
                "http://fakes3:4569/fakebucket.with.periods/v1/raw_crash/20160918/"
                + "de1bb258-cbbf-4589-a673-34f800160918"
            ),
            # Not going to compare the body here because it's just the raw crash
            resp=s3mock.fake_response(status_code=200),
        )
        data, headers = multipart_encode(
            {
                "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
                "ProductName": "Firefox",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app(
            {
                "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.s3.crashstorage.S3CrashStorage",
                "CRASHMOVER_CRASHSTORAGE_ENDPOINT_URL": "http://fakes3:4569",
                "CRASHMOVER_CRASHSTORAGE_REGION": "us-west-1",
                "CRASHMOVER_CRASHSTORAGE_ACCESS_KEY": "fakekey",
                "CRASHMOVER_CRASHSTORAGE_SECRET_ACCESS_KEY": "fakesecretkey",
                "CRASHMOVER_CRASHSTORAGE_BUCKET_NAME": "fakebucket.with.periods",
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)
        client.join_app()

        # Verify the collector returns a 200 status code and the crash id
        # we fed it.
        assert result.status_code == 200
        assert result.content == b"CrashID=bp-de1bb258-cbbf-4589-a673-34f800160918\n"

        # Assert we did the entire s3 conversation
        assert s3mock.remaining_conversation() == []

    def test_missing_bucket_halts_startup(
        self, client, s3mock, mock_generate_test_filepath
    ):
        # .verify_write_to_bucket() writes to the bucket to verify Antenna can
        # write to it and the configuration is correct
        s3mock.add_step(
            method="PUT",
            url="http://fakes3:4569/fakebucket/test/testwrite.txt",
            body=b"test",
            resp=s3mock.fake_response(status_code=404),
        )

        with pytest.raises(botocore.exceptions.ClientError) as excinfo:
            # Rebuild the app the test client is using with relevant
            # configuration. This calls .verify_write_to_bucket() which fails.
            client.rebuild_app(
                {
                    "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.s3.crashstorage.S3CrashStorage",
                    "CRASHMOVER_CRASHSTORAGE_ENDPOINT_URL": "http://fakes3:4569",
                    "CRASHMOVER_CRASHSTORAGE_ACCESS_KEY": "fakekey",
                    "CRASHMOVER_CRASHSTORAGE_SECRET_ACCESS_KEY": "fakesecretkey",
                    "CRASHMOVER_CRASHSTORAGE_BUCKET_NAME": "fakebucket",
                }
            )

        assert (
            "An error occurred (404) when calling the PutObject operation: Not Found"
            in str(excinfo.value)
        )

        # Assert we did the entire s3 conversation
        assert s3mock.remaining_conversation() == []

    def test_retrying(self, client, s3mock, caplog, mock_generate_test_filepath):
        # .verify_write_to_bucket() writes to the bucket to verify Antenna can
        # write to it and the configuration is correct
        s3mock.add_step(
            method="PUT",
            url="http://fakes3:4569/fakebucket/test/testwrite.txt",
            body=b"test",
            resp=s3mock.fake_response(status_code=200),
        )

        # Fail once with a 403, retry and then proceed.
        s3mock.add_step(
            method="PUT",
            url=(
                "http://fakes3:4569/fakebucket/v1/dump_names/"
                "de1bb258-cbbf-4589-a673-34f800160918"
            ),
            body=b'["upload_file_minidump"]',
            resp=s3mock.fake_response(status_code=403),
        )

        # Proceed with saving files.
        s3mock.add_step(
            method="PUT",
            url=(
                "http://fakes3:4569/fakebucket/v1/dump_names/"
                "de1bb258-cbbf-4589-a673-34f800160918"
            ),
            body=b'["upload_file_minidump"]',
            resp=s3mock.fake_response(status_code=200),
        )
        s3mock.add_step(
            method="PUT",
            url=(
                "http://fakes3:4569/fakebucket/v1/dump/"
                "de1bb258-cbbf-4589-a673-34f800160918"
            ),
            body=b"abcd1234",
            resp=s3mock.fake_response(status_code=200),
        )
        s3mock.add_step(
            method="PUT",
            url=(
                "http://fakes3:4569/fakebucket/v1/raw_crash/"
                + "20160918/de1bb258-cbbf-4589-a673-34f800160918"
            ),
            # Not going to compare the body here because it's just the raw crash
            resp=s3mock.fake_response(status_code=200),
        )
        data, headers = multipart_encode(
            {
                "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
                "ProductName": "Firefox",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app(
            {
                "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.s3.crashstorage.S3CrashStorage",
                "CRASHMOVER_CRASHSTORAGE_ENDPOINT_URL": "http://fakes3:4569",
                "CRASHMOVER_CRASHSTORAGE_ACCESS_KEY": "fakekey",
                "CRASHMOVER_CRASHSTORAGE_SECRET_ACCESS_KEY": "fakesecretkey",
                "CRASHMOVER_CRASHSTORAGE_BUCKET_NAME": "fakebucket",
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)
        client.join_app()

        # Verify the collector returns a 200 status code and the crash id
        # we fed it.
        assert result.status_code == 200
        assert result.content == b"CrashID=bp-de1bb258-cbbf-4589-a673-34f800160918\n"

        # Verify the retry decorator logged something
        records = [
            rec for rec in caplog.record_tuples if rec[0] == "antenna.ext.s3.connection"
        ]
        assert records == [
            (
                "antenna.ext.s3.connection",
                logging.WARNING,
                (
                    "S3Connection.save_file: exception An error occurred (403) "
                    "when calling the PutObject operation: Forbidden, retry attempt 0"
                ),
            )
        ]

        # Assert we did the entire s3 conversation
        assert s3mock.remaining_conversation() == []

    # FIXME(willkg): Add test for bad region
    # FIXME(willkg): Add test for invalid credentials
