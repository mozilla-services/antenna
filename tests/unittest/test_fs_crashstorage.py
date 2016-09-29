# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import os
import time

import mock


MOCK_DATETIME = datetime.datetime(2011, 9, 6, 0, 0, 0, tzinfo=datetime.timezone.utc)
MOCK_TIME = time.mktime(MOCK_DATETIME.timetuple())


def get_tree(path):
    """Builds a list of files in a directory tree"""
    all_files = []
    for root, dirs, files in os.walk(path):
        all_files.extend([os.path.join(root, fn) for fn in files])

    return all_files


class TestFSCrashStorage:
    @mock.patch('antenna.app.time')
    @mock.patch('antenna.app.utc_now')
    def test_storage_files(self, mock_utc_now, mock_time, client, payload_generator, tmpdir):
        """Verify posting a crash gets to crash storage in the right shape"""
        mock_utc_now.return_value = MOCK_DATETIME
        mock_time.time.return_value = MOCK_TIME

        boundary, data = payload_generator('socorrofake1_withuuid.raw')

        # Rebuild the app the test client is using with relevant configuration.
        client.rebuild_app({
            'BASEDIR': str(tmpdir),
            'FS_ROOT': str(tmpdir.join('antenna_crashes')),
            'CRASHSTORAGE_CLASS': 'antenna.external.fs.crashstorage.FSCrashStorage'
        })

        result = client.post(
            '/submit',
            headers={
                'Content-Type': 'multipart/form-data; boundary=' + boundary,
            },
            body=data
        )

        assert result.status_code == 200

        files = get_tree(str(tmpdir))

        def nix_tmpdir(fn):
            """Removes the tmpdir portion from the beginning of the path"""
            return fn[len(str(tmpdir)):]

        # Verify the set of files in the directory match what FSCrashStorage
        # should have written--no more and no less.
        assert (
            sorted([nix_tmpdir(fn) for fn in files]) ==
            sorted([
                '/antenna_crashes/20160918/raw_crash/de1bb258-cbbf-4589-a673-34f802160918.json',
                '/antenna_crashes/20160918/dump_names/de1bb258-cbbf-4589-a673-34f802160918.json',
                '/antenna_crashes/20160918/upload_file_minidump/de1bb258-cbbf-4589-a673-34f802160918',
            ])
        )

        contents = {}
        for fn in files:
            with open(fn, 'rb') as fp:
                contents[nix_tmpdir(fn)] = fp.read()

        print(contents)

        assert (
            contents['/antenna_crashes/20160918/raw_crash/de1bb258-cbbf-4589-a673-34f802160918.json'] ==
            (
                b'{"ProductName": "Test", ' +
                b'"Version": "1.0", ' +
                b'"dump_checksums": {"upload_file_minidump": "e19d5cd5af0378da05f63f891c7467af"}, ' +
                b'"submitted_timestamp": "2011-09-06T00:00:00+00:00", ' +
                b'"timestamp": 1315267200.0, ' +
                b'"type_tag": "bp", ' +
                b'"uuid": "de1bb258-cbbf-4589-a673-34f802160918"}'
            )
        )

        assert (
            contents['/antenna_crashes/20160918/dump_names/de1bb258-cbbf-4589-a673-34f802160918.json'] ==
            b'["upload_file_minidump"]'
        )

        assert (
            contents['/antenna_crashes/20160918/upload_file_minidump/de1bb258-cbbf-4589-a673-34f802160918'] ==
            b'abcd1234'
        )
