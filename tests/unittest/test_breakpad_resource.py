# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import io

from everett.manager import ConfigManager
import pytest

from antenna.app import BreakpadSubmitterResource
from antenna.breakpad_resource import MAX_ATTEMPTS
from antenna.ext.crashstorage_base import CrashStorageBase
from testlib.mini_poster import compress, multipart_encode


class BadCrashStorage(CrashStorageBase):
    def save_dumps(self, crash_id, dumps):
        raise Exception

    def save_raw_crash(self, crash_id, raw_crash):
        raise Exception


class TestBreakpadSubmitterResource:
    empty_config = ConfigManager.from_dict({})

    def test_submit_crash_report_reply(self, client):
        data, headers = multipart_encode({
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        })

        result = client.simulate_post(
            '/submit',
            headers=headers,
            body=data,
        )
        assert result.status_code == 200
        assert result.headers['Content-Type'].startswith('text/plain')
        assert result.content.startswith(b'CrashID=bp')

    def test_extract_payload(self, request_generator):
        data, headers = multipart_encode({
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        })
        req = request_generator(
            method='POST',
            path='/submit',
            headers=headers,
            body=data,
        )

        bsp = BreakpadSubmitterResource(self.empty_config)
        expected_raw_crash = {
            'ProductName': 'Test',
            'Version': '1.0',
            'dump_checksums': {
                'upload_file_minidump': 'e19d5cd5af0378da05f63f891c7467af',
            }
        }
        expected_dumps = {
            'upload_file_minidump': b'abcd1234'
        }
        assert bsp.extract_payload(req) == (expected_raw_crash, expected_dumps)

    def test_extract_payload_2_dumps(self, request_generator):
        data, headers = multipart_encode({
            'ProductName': 'Test',
            'Version': '1',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'deadbeef')),
            'upload_file_minidump_flash1': ('fakecrash2.dump', io.BytesIO(b'abcd1234')),
        })

        req = request_generator(
            method='POST',
            path='/submit',
            headers=headers,
            body=data,
        )

        bsp = BreakpadSubmitterResource(self.empty_config)
        expected_raw_crash = {
            'ProductName': 'Test',
            'Version': '1',
            'dump_checksums': {
                'upload_file_minidump': '4f41243847da693a4f356c0486114bc6',
                'upload_file_minidump_flash1': 'e19d5cd5af0378da05f63f891c7467af',
            }
        }
        expected_dumps = {
            'upload_file_minidump': b'deadbeef',
            'upload_file_minidump_flash1': b'abcd1234'
        }
        assert bsp.extract_payload(req) == (expected_raw_crash, expected_dumps)

    def test_extract_payload_compressed(self, request_generator):
        data, headers = multipart_encode({
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        })

        data = compress(data)
        headers['Content-Encoding'] = 'gzip'

        req = request_generator(
            method='POST',
            path='/submit',
            headers=headers,
            body=data,
        )

        bsp = BreakpadSubmitterResource(self.empty_config)
        expected_raw_crash = {
            'ProductName': 'Test',
            'Version': '1.0',
            'dump_checksums': {
                'upload_file_minidump': 'e19d5cd5af0378da05f63f891c7467af',
            }
        }
        expected_dumps = {
            'upload_file_minidump': b'abcd1234'
        }
        assert bsp.extract_payload(req) == (expected_raw_crash, expected_dumps)

    @pytest.mark.parametrize('data, expected_raw_crash, expected_dumps', [
        ({'ProductName': 'Firefox'}, {'ProductName': 'Firefox'}, {}),

        # In the key...
        ({'\u0000ProductName': 'Firefox'}, {'ProductName': 'Firefox'}, {}),

        # In the value...
        ({'ProductName': 'Firefox\u0000'}, {'ProductName': 'Firefox'}, {}),

        # In the dump filename...
        (
            {'ProductName': 'Firefox', '\u0000upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'deadbeef'))},
            {'ProductName': 'Firefox', 'dump_checksums': {'upload_file_minidump': '4f41243847da693a4f356c0486114bc6'}},
            {'upload_file_minidump': b'deadbeef'}
        )
    ])
    def test_extract_payload_with_nulls(self, data, expected_raw_crash, expected_dumps, request_generator):
        data, headers = multipart_encode(data)

        req = request_generator(
            method='POST',
            path='/submit',
            headers=headers,
            body=data,
        )

        bsp = BreakpadSubmitterResource(self.empty_config)
        assert bsp.extract_payload(req) == (expected_raw_crash, expected_dumps)

    def test_existing_uuid(self, client):
        crash_id = 'de1bb258-cbbf-4589-a673-34f800160918'
        data, headers = multipart_encode({
            'uuid': crash_id,
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        })

        result = client.simulate_post(
            '/submit',
            headers=headers,
            body=data
        )
        assert result.status_code == 200

        # Extract the uuid from the response content and verify that it's the
        # crash id we sent
        assert result.content.decode('utf-8') == 'CrashID=bp-%s\n' % crash_id

    def test_legacy_processing(self, client, loggingmock):
        # NOTE(willkg): This encodes throttle result which is 0 (ACCEPT)
        crash_id = 'de1bb258-cbbf-4589-a673-34f800160918'

        data, headers = multipart_encode({
            'uuid': crash_id,
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234')),

            'legacy_processing': '0',  # ACCEPT
            'throttle_rate': '100',
        })

        with loggingmock(['antenna']) as lm:
            result = client.simulate_post(
                '/submit',
                headers=headers,
                body=data
            )
            assert result.status_code == 200

            assert lm.has_record(
                name='antenna.breakpad_resource',
                levelname='INFO',
                msg_contains='%s: matched by FROM_CRASHID; returned ACCEPT' % crash_id
            )

    @pytest.mark.parametrize('legacy,throttle_rate', [
        # One of the two is a non-int
        ('foo', 'bar'),
        ('0', 'bar'),
        ('foo', '100'),

        # legacy_processing is not a valid value
        ('1000', '100'),

        # throttle_rate is not valid
        ('0', '1000')
    ])
    def test_legacy_processing_bad_values(self, legacy, throttle_rate, client, loggingmock):
        data, headers = multipart_encode({
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234')),

            # These are invalid values for legacy_processing and throttle_rate
            'legacy_processing': legacy,
            'throttle_rate': throttle_rate
        })

        with loggingmock(['antenna']) as lm:
            result = client.simulate_post(
                '/submit',
                headers=headers,
                body=data
            )
            assert result.status_code == 200

            # Verify it didn't match with ALREADY_THROTTLED and instead matched
            # with a rule indicating it went through throttling.
            assert lm.has_record(
                name='antenna.breakpad_resource',
                levelname='INFO',
                msg_contains='matched by is_thunderbird_seamonkey; returned ACCEPT'
            )

    def test_throttleable(self, client, loggingmock):
        data, headers = multipart_encode({
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234')),

            'Throttleable': '0'
        })

        with loggingmock(['antenna']) as lm:
            result = client.simulate_post(
                '/submit',
                headers=headers,
                body=data
            )
            assert result.status_code == 200

            # Verify it got matched as a THROTTLEABLE_0
            assert lm.has_record(
                name='antenna.breakpad_resource',
                levelname='INFO',
                msg_contains='matched by THROTTLEABLE_0; returned ACCEPT'
            )

    def test_queuing(self, client):
        def check_health(crashmover_pool_size, crashmover_save_queue_size):
            bpr = client.get_resource_by_name('breakpad')
            assert len(bpr.crashmover_save_queue) == crashmover_save_queue_size
            assert len(bpr.crashmover_pool) == crashmover_pool_size

        # Rebuild the app so the client only saves one crash at a time to s3
        client.rebuild_app({
            'CONCURRENT_SAVES': '1'
        })

        data, headers = multipart_encode({
            'uuid': 'de1bb258-cbbf-4589-a673-34f800160918',
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        })

        # Verify initial conditions are correct--no active coroutines and
        # nothing in the save queue
        check_health(crashmover_pool_size=0, crashmover_save_queue_size=0)

        # Submit a crash
        client.simulate_post('/submit', headers=headers, body=data)
        # Now there's one coroutine active and one item in the save queue
        check_health(crashmover_pool_size=1, crashmover_save_queue_size=1)

        # Submit another crash
        client.simulate_post('/submit', headers=headers, body=data)
        # The coroutine hasn't run yet (we haven't called .join), so there's
        # one coroutine and two queued crashes
        check_health(crashmover_pool_size=2, crashmover_save_queue_size=2)

        # Now join the app and let the coroutines run and make sure the queue clears
        client.join_app()
        # No more coroutines and no more save queue
        check_health(crashmover_pool_size=0, crashmover_save_queue_size=0)

    def test_retry(self, client, loggingmock):
        crash_id = 'de1bb258-cbbf-4589-a673-34f800160918'
        data, headers = multipart_encode({
            'uuid': crash_id,
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        })

        client.rebuild_app({
            'CRASHSTORAGE_CLASS': BadCrashStorage.__module__ + '.' + BadCrashStorage.__name__,
        })

        with loggingmock(['antenna']) as lm:
            result = client.simulate_post(
                '/submit',
                headers=headers,
                body=data
            )
            assert result.status_code == 200

            # The storage is bad, so this should raise errors and then log something
            client.join_app()

            # We're using BadCrashStorage so the crashmover should retry 20
            # times logging a message each time and then give up
            for i in range(1, MAX_ATTEMPTS):
                assert lm.has_record(
                    name='antenna.breakpad_resource',
                    levelname='ERROR',
                    msg_contains=(
                        'Exception when processing save queue (%s); error %d/%d' % (
                            crash_id,
                            i,
                            MAX_ATTEMPTS
                        )
                    )
                )
