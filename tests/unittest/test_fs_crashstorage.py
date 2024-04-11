# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import io
import os

from freezegun import freeze_time
import pytest

from antenna.ext.crashstorage_base import CrashIDNotFound
from testlib.mini_poster import multipart_encode


def get_tree(path):
    """Builds a list of files in a directory tree"""
    all_files = []
    for root, _, files in os.walk(path):
        all_files.extend([os.path.join(root, fn) for fn in files])

    return all_files


class TestFSCrashStorage:
    @freeze_time("2011-09-06 00:00:00", tz_offset=0)
    def test_crashmover_save(self, client, tmpdir):
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
                "BREAKPAD_THROTTLER_RULES": "antenna.throttler.ACCEPT_ALL",
                "BREAKPAD_THROTTLER_PRODUCTS": "antenna.throttler.ALL_PRODUCTS",
                "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.fs.crashstorage.FSCrashStorage",
                "CRASHMOVER_CRASHSTORAGE_FS_ROOT": str(tmpdir.join("antenna_crashes")),
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)

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
            b"{"
            + b'"ProductName": "Test", '
            + b'"Version": "1.0", '
            + b'"metadata": {'
            + b'"collector_notes": [], '
            + b'"dump_checksums": '
            + b'{"upload_file_minidump": "e9cee71ab932fde863338d08be4de9dfe39ea049bdafb342ce659ec5450b69ae"}, '
            + b'"payload": "multipart", '
            + b'"payload_compressed": "0", '
            + b'"payload_size": 645, '
            + b'"throttle_rule": "accept_everything"'
            + b"}, "
            + b'"submitted_timestamp": "2011-09-06T00:00:00+00:00", '
            + b'"uuid": "de1bb258-cbbf-4589-a673-34f800160918", '
            + b'"version": 2'
            + b"}"
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

    @freeze_time("2011-09-06 00:00:00", tz_offset=0)
    def test_load_crash(self, client, tmpdir):
        crash_id = "de1bb258-cbbf-4589-a673-34f800110906"
        data, headers = multipart_encode(
            {
                "uuid": crash_id,
                "ProductName": "Test",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app(
            {
                "BASEDIR": str(tmpdir),
                "BREAKPAD_THROTTLER_RULES": "antenna.throttler.ACCEPT_ALL",
                "BREAKPAD_THROTTLER_PRODUCTS": "antenna.throttler.ALL_PRODUCTS",
                "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.fs.crashstorage.FSCrashStorage",
                "CRASHMOVER_CRASHSTORAGE_FS_ROOT": str(tmpdir.join("antenna_crashes")),
            }
        )

        result = client.simulate_post("/submit", headers=headers, body=data)

        assert result.status_code == 200

        fs_crashstorage = client.get_crashmover().crashstorage
        crash_report = fs_crashstorage.load_crash(crash_id)
        assert crash_report.crash_id == crash_id
        assert crash_report.dumps == {"upload_file_minidump": b"abcd1234"}
        assert crash_report.raw_crash == {
            "uuid": crash_id,
            "ProductName": "Test",
            "Version": "1.0",
            "metadata": {
                "collector_notes": [],
                "dump_checksums": {
                    "upload_file_minidump": "e9cee71ab932fde863338d08be4de9dfe39ea049bdafb342ce659ec5450b69ae"
                },
                "payload": "multipart",
                "payload_compressed": "0",
                "payload_size": 645,
                "throttle_rule": "accept_everything",
            },
            "submitted_timestamp": "2011-09-06T00:00:00+00:00",
            "version": 2,
        }

    def test_load_file_not_found(self, client, tmpdir):
        crash_id = "de1bb258-cbbf-4589-a673-34f800110906"

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app(
            {
                "BASEDIR": str(tmpdir),
                "BREAKPAD_THROTTLER_RULES": "antenna.throttler.ACCEPT_ALL",
                "BREAKPAD_THROTTLER_PRODUCTS": "antenna.throttler.ALL_PRODUCTS",
                "CRASHMOVER_CRASHSTORAGE_CLASS": "antenna.ext.fs.crashstorage.FSCrashStorage",
                "CRASHMOVER_CRASHSTORAGE_FS_ROOT": str(tmpdir.join("antenna_crashes")),
            }
        )

        fs_crashstorage = client.get_crashmover().crashstorage
        with pytest.raises(CrashIDNotFound):
            fs_crashstorage.load_crash(crash_id)
