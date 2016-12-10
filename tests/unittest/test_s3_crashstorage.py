import io

import botocore
import pytest

from testlib.mini_poster import multipart_encode


class TestS3Mock:
    def test_crash_storage(self, client, s3mock):
        # .verify_configuration() calls HEAD on the bucket to verify it exists
        # and the configuration is correct.
        s3mock.add_step(
            method='HEAD',
            url='http://fakes3:4569/fakebucket',
            resp=s3mock.fake_response(status_code=200)
        )

        # # We want to verify these files are saved in this specific order.
        s3mock.add_step(
            method='PUT',
            url='http://fakes3:4569/fakebucket//v1/dump_names/de1bb258-cbbf-4589-a673-34f800160918',
            body=b'["upload_file_minidump"]',
            resp=s3mock.fake_response(status_code=200)
        )
        s3mock.add_step(
            method='PUT',
            url='http://fakes3:4569/fakebucket//v1/upload_file_minidump/de1bb258-cbbf-4589-a673-34f800160918',
            body=b'abcd1234',
            resp=s3mock.fake_response(status_code=200)
        )
        s3mock.add_step(
            method='PUT',
            url='http://fakes3:4569/fakebucket//v2/raw_crash/de1/20160918/de1bb258-cbbf-4589-a673-34f800160918',
            # Not going to compare the body here because it's just the raw crash
            resp=s3mock.fake_response(status_code=200)
        )
        data, headers = multipart_encode({
            'uuid': 'de1bb258-cbbf-4589-a673-34f800160918',
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        })

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app({
            'CRASHSTORAGE_CLASS': 'antenna.ext.s3.crashstorage.S3CrashStorage',
            'CRASHSTORAGE_ENDPOINT_URL': 'http://fakes3:4569',
            'CRASHSTORAGE_ACCESS_KEY': 'fakekey',
            'CRASHSTORAGE_SECRET_ACCESS_KEY': 'fakesecretkey',
            'CRASHSTORAGE_BUCKET_NAME': 'fakebucket',
        })

        result = client.simulate_post(
            '/submit',
            headers=headers,
            body=data
        )
        client.join_app()

        # Verify the collector returns a 200 status code and the crash id
        # we fed it.
        assert result.status_code == 200
        assert result.content == b'CrashID=bp-de1bb258-cbbf-4589-a673-34f800160918\n'

    def test_region_and_bucket_with_periods(self, client, s3mock):
        # # .verify_configuration() calls HEAD on the bucket to verify it exists
        # # and the configuration is correct.
        ROOT = 'https://s3-us-west-1.amazonaws.com/'
        s3mock.add_step(
            method='HEAD',
            url=ROOT + 'fakebucket.with.periods',
            resp=s3mock.fake_response(status_code=200)
        )

        # We want to verify these files are saved in this specific order.
        s3mock.add_step(
            method='PUT',
            url=ROOT + 'fakebucket.with.periods//v1/dump_names/de1bb258-cbbf-4589-a673-34f800160918',
            body=b'["upload_file_minidump"]',
            resp=s3mock.fake_response(status_code=200)
        )
        s3mock.add_step(
            method='PUT',
            url=ROOT + 'fakebucket.with.periods//v1/upload_file_minidump/de1bb258-cbbf-4589-a673-34f800160918',
            body=b'abcd1234',
            resp=s3mock.fake_response(status_code=200)
        )
        s3mock.add_step(
            method='PUT',
            url=ROOT + 'fakebucket.with.periods//v2/raw_crash/de1/20160918/de1bb258-cbbf-4589-a673-34f800160918',
            # Not going to compare the body here because it's just the raw crash
            resp=s3mock.fake_response(status_code=200)
        )
        data, headers = multipart_encode({
            'uuid': 'de1bb258-cbbf-4589-a673-34f800160918',
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        })

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app({
            'CRASHSTORAGE_CLASS': 'antenna.ext.s3.crashstorage.S3CrashStorage',
            'CRASHSTORAGE_REGION': 'us-west-1',
            'CRASHSTORAGE_ACCESS_KEY': 'fakekey',
            'CRASHSTORAGE_SECRET_ACCESS_KEY': 'fakesecretkey',
            'CRASHSTORAGE_BUCKET_NAME': 'fakebucket.with.periods',
        })

        result = client.simulate_post(
            '/submit',
            headers=headers,
            body=data
        )
        client.join_app()

        # Verify the collector returns a 200 status code and the crash id
        # we fed it.
        assert result.status_code == 200
        assert result.content == b'CrashID=bp-de1bb258-cbbf-4589-a673-34f800160918\n'

    def test_missing_bucket_halts_startup(self, client, s3mock):
        # .verify_configuration() calls HEAD on the bucket to verify it exists
        # and the configuration is correct. This fails for here.
        s3mock.add_step(
            method='HEAD',
            url='http://fakes3:4569/fakebucket',
            resp=s3mock.fake_response(status_code=404)
        )

        with pytest.raises(botocore.exceptions.ClientError) as excinfo:
            # Rebuild the app the test client is using with relevant
            # configuration. This calls .verify_configuration() which fails.
            client.rebuild_app({
                'CRASHSTORAGE_CLASS': 'antenna.ext.s3.crashstorage.S3CrashStorage',
                'CRASHSTORAGE_ENDPOINT_URL': 'http://fakes3:4569',
                'CRASHSTORAGE_ACCESS_KEY': 'fakekey',
                'CRASHSTORAGE_SECRET_ACCESS_KEY': 'fakesecretkey',
                'CRASHSTORAGE_BUCKET_NAME': 'fakebucket',
            })

        assert (
            'An error occurred (404) when calling the HeadBucket operation: Not Found'
            in str(excinfo.value)
        )


class TestS3MockLogging:
    logging_names = ['antenna']

    def test_retrying(self, client, s3mock, loggingmock):
        ROOT = 'http://fakes3:4569/'

        # .verify_configuration() calls HEAD on the bucket to verify it exists
        # and the configuration is correct.
        s3mock.add_step(
            method='HEAD',
            url=ROOT + 'fakebucket',
            resp=s3mock.fake_response(status_code=200)
        )

        # Fail once with a 403, retry and then proceed.
        s3mock.add_step(
            method='PUT',
            url=ROOT + 'fakebucket//v1/dump_names/de1bb258-cbbf-4589-a673-34f800160918',
            body=b'["upload_file_minidump"]',
            resp=s3mock.fake_response(status_code=403)
        )

        # Proceed with saving files.
        s3mock.add_step(
            method='PUT',
            url=ROOT + 'fakebucket//v1/dump_names/de1bb258-cbbf-4589-a673-34f800160918',
            body=b'["upload_file_minidump"]',
            resp=s3mock.fake_response(status_code=200)
        )
        s3mock.add_step(
            method='PUT',
            url=ROOT + 'fakebucket//v1/upload_file_minidump/de1bb258-cbbf-4589-a673-34f800160918',
            body=b'abcd1234',
            resp=s3mock.fake_response(status_code=200)
        )
        s3mock.add_step(
            method='PUT',
            url=ROOT + 'fakebucket//v2/raw_crash/de1/20160918/de1bb258-cbbf-4589-a673-34f800160918',
            # Not going to compare the body here because it's just the raw crash
            resp=s3mock.fake_response(status_code=200)
        )
        data, headers = multipart_encode({
            'uuid': 'de1bb258-cbbf-4589-a673-34f800160918',
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        })

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app({
            'CRASHSTORAGE_CLASS': 'antenna.ext.s3.crashstorage.S3CrashStorage',
            'CRASHSTORAGE_ENDPOINT_URL': 'http://fakes3:4569',
            'CRASHSTORAGE_ACCESS_KEY': 'fakekey',
            'CRASHSTORAGE_SECRET_ACCESS_KEY': 'fakesecretkey',
            'CRASHSTORAGE_BUCKET_NAME': 'fakebucket',
        })

        with loggingmock(['antenna']) as lm:
            result = client.simulate_post(
                '/submit',
                headers=headers,
                body=data
            )
            client.join_app()

            # Verify the collector returns a 200 status code and the crash id
            # we fed it.
            assert result.status_code == 200
            assert result.content == b'CrashID=bp-de1bb258-cbbf-4589-a673-34f800160918\n'

            # Verify the retry decorator logged something
            assert lm.has_record(
                name='antenna.ext.s3.connection',
                levelname='ERROR',
                msg_contains='retry attempt 0'
            )

    # FIXME(willkg): Add test for bad region
    # FIXME(willkg): Add test for invalid credentials
