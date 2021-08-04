# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import io

from freezegun import freeze_time

from testlib.mini_poster import multipart_encode


class TestCrashStorage:
    @freeze_time("2011-09-06 00:00:00", tz_offset=0)
    def test_flow(self, client):
        """Verify posting a crash gets to crash storage in the right shape"""
        client.rebuild_app(
            {
                "BREAKPAD_THROTTLER_RULES": "antenna.throttler.ACCEPT_ALL",
                "BREAKPAD_THROTTLER_PRODUCTS": "antenna.throttler.ALL_PRODUCTS",
            }
        )

        data, headers = multipart_encode(
            {
                "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
                "ProductName": "Test",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)
        client.join_app()
        assert result.status_code == 200

        crashmover = client.get_crashmover()

        # Now we've got the CrashMover, so we can pull out the crashstorage, verify
        # there's only one crash in it and then verify the contents of the crash.

        # Verify things got saved
        assert crashmover.crashstorage.saved_things == [
            {"crash_id": "de1bb258-cbbf-4589-a673-34f800160918"}
        ]

        # Verify things got published
        assert crashmover.crashpublish.published_things == [
            {"crash_id": "de1bb258-cbbf-4589-a673-34f800160918"}
        ]
