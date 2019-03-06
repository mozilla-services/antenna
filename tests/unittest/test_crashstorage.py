# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import io

from freezegun import freeze_time

from testlib.mini_poster import multipart_encode


class TestCrashStorage:
    @freeze_time('2011-09-06 00:00:00', tz_offset=0)
    def test_flow(self, client):
        """Verify posting a crash gets to crash storage in the right shape"""
        client.rebuild_app({
            'THROTTLE_RULES': 'antenna.throttler.ACCEPT_ALL',
            'PRODUCTS': 'antenna.throttler.ALL_PRODUCTS'
        })

        data, headers = multipart_encode({
            'uuid': 'de1bb258-cbbf-4589-a673-34f800160918',
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        })

        result = client.simulate_post(
            '/submit',
            headers=headers,
            body=data
        )
        client.join_app()
        assert result.status_code == 200

        bsr = client.get_resource_by_name('breakpad')

        # Now we've got the BreakpadSubmitterResource, so we can pull out the
        # crashstorage, verify there's only one crash in it and then verify the
        # contents of the crash.
        crashstorage = bsr.crashstorage
        # 1 raw crash and 1 dump
        assert len(crashstorage.saved_things) == 2

        # First thing is the dump
        assert (
            crashstorage.saved_things[0] ==
            {
                'crash_id': 'de1bb258-cbbf-4589-a673-34f800160918',
                'type': 'upload_file_minidump',
                'data': b'abcd1234'
            }
        )

        # Second thing is the raw crash metadata
        assert (
            crashstorage.saved_things[1] ==
            {
                'crash_id': 'de1bb258-cbbf-4589-a673-34f800160918',
                'type': 'raw_crash',
                'data': {
                    'ProductName': 'Test',
                    'Version': '1.0',
                    'dump_checksums': {
                        'upload_file_minidump': 'e9cee71ab932fde863338d08be4de9dfe39ea049bdafb342ce659ec5450b69ae'
                    },
                    'legacy_processing': 0,
                    'MinidumpSha256Hash': 'e9cee71ab932fde863338d08be4de9dfe39ea049bdafb342ce659ec5450b69ae',
                    'throttle_rate': 100,
                    'submitted_timestamp': '2011-09-06T00:00:00+00:00',
                    'timestamp': 1315267200.0,
                    'type_tag': 'bp',
                    'uuid': 'de1bb258-cbbf-4589-a673-34f800160918'
                }
            }
        )

        crashpublish = bsr.crashpublish
        # 1 crash id
        assert (
            crashpublish.published_things == [
                {'crash_id': 'de1bb258-cbbf-4589-a673-34f800160918'}
            ]
        )
