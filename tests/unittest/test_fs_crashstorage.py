# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import io
import os

from freezegun import freeze_time

from testlib.mini_poster import multipart_encode


def get_tree(path):
    """Builds a list of files in a directory tree"""
    all_files = []
    for root, dirs, files in os.walk(path):
        all_files.extend([os.path.join(root, fn) for fn in files])

    return all_files


class TestFSCrashStorage:
    @freeze_time("2011-09-06 00:00:00", tz_offset=0)
    def test_storage_files(self, client, tmpdir):
        """Verify posting a crash gets to crash storage in the right shape"""
        data, headers = multipart_encode(
            {
                "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
                "ProductName": "Test",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app(
            {
                "BASEDIR": str(tmpdir),
                "THROTTLE_RULES": "antenna.throttler.ACCEPT_ALL",
                "PRODUCTS": "antenna.throttler.ALL_PRODUCTS",
                "CRASHSTORAGE_CLASS": "antenna.ext.fs.crashstorage.FSCrashStorage",
                "CRASHSTORAGE_FS_ROOT": str(tmpdir.join("antenna_crashes")),
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)
        client.join_app()

        assert result.status_code == 200

        files = get_tree(str(tmpdir))

        def nix_tmpdir(fn):
            """Removes the tmpdir portion from the beginning of the path"""
            return fn[len(str(tmpdir)) :]

        # Verify the set of files in the directory match what FSCrashStorage
        # should have written--no more and no less.
        assert sorted([nix_tmpdir(fn) for fn in files]) == sorted(
            [
                "/antenna_crashes/20160918/raw_crash/de1bb258-cbbf-4589-a673-34f800160918.json",
                "/antenna_crashes/20160918/dump_names/de1bb258-cbbf-4589-a673-34f800160918.json",
                "/antenna_crashes/20160918/upload_file_minidump/de1bb258-cbbf-4589-a673-34f800160918",
            ]
        )

        contents = {}
        for fn in files:
            with open(fn, "rb") as fp:
                contents[nix_tmpdir(fn)] = fp.read()

        assert contents[
            "/antenna_crashes/20160918/raw_crash/de1bb258-cbbf-4589-a673-34f800160918.json"
        ] == (
            b'{"MinidumpSha256Hash": "e9cee71ab932fde863338d08be4de9dfe39ea049bdafb342ce659ec5450b69ae", '
            + b'"ProductName": "Test", '
            + b'"Version": "1.0", '
            + b'"dump_checksums": '
            + b'{"upload_file_minidump": "e9cee71ab932fde863338d08be4de9dfe39ea049bdafb342ce659ec5450b69ae"}, '
            + b'"legacy_processing": 0, '
            + b'"payload": "multipart", '
            + b'"submitted_timestamp": "2011-09-06T00:00:00+00:00", '
            + b'"throttle_rate": 100, '
            + b'"timestamp": 1315267200.0, '
            + b'"type_tag": "bp", '
            + b'"uuid": "de1bb258-cbbf-4589-a673-34f800160918"}'
        )

        assert (
            contents[
                "/antenna_crashes/20160918/dump_names/de1bb258-cbbf-4589-a673-34f800160918.json"
            ]
            == b'["upload_file_minidump"]'
        )

        assert (
            contents[
                "/antenna_crashes/20160918/upload_file_minidump/de1bb258-cbbf-4589-a673-34f800160918"
            ]
            == b"abcd1234"
        )
