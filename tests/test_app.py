# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import gzip
import io
import os.path

import pytest

from antenna.app import BreakpadSubmitterResource


class TestHealthCheckResource:
    def test_good(self, client):
        result = client.get('/api/v1/health')
        assert result.json['health'] == 'v1'


def fetch_payload(datadir, fn):
    with open(os.path.join(datadir, fn), 'r') as fp:
        data = fp.read()

    # Fix newlines
    data = data.replace('\n', '\r\n')
    # Figure out the boundary for this file. It's the first line minus two of
    # the - at the beinning.
    boundary = data.splitlines()[0].strip()[2:]
    return boundary, data


class FauxStorage:
    def __init__(self, config):
        self.stored = []

    def save_raw_crash(self, *args, **kwargs):
        self.stored.append((args, kwargs))


class TestBreakpadSubmitterResource:
    config_vars = {}

    def test_submit_crash_report_reply(self, datadir, client):
        boundary, data = fetch_payload(datadir, 'socorrofake1.raw')

        result = client.post(
            '/submit',
            headers={
                'Content-Type': 'multipart/form-data; boundary=' + boundary,
            },
            body=data
        )
        assert result.status_code == 200
        assert result.content.startswith(b'CrashID=bp')

    def test_extract_payload(self, datadir, config, request_generator):
        boundary, data = fetch_payload(datadir, 'socorrofake1.raw')
        req = request_generator(
            method='POST',
            path='/submit',
            headers={
                'Content-Type': 'multipart/form-data; boundary=' + boundary,
            },
            body=data,
        )

        bsp = BreakpadSubmitterResource(config)
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

    def test_extract_payload_compressed(self, datadir, config, request_generator):
        boundary, data = fetch_payload(datadir, 'socorrofake1.raw')

        # Compress the payload
        bio = io.BytesIO()
        g = gzip.GzipFile(fileobj=bio, mode='w')
        g.write(data.encode('utf-8'))
        g.close()
        data = bio.getbuffer()

        req = request_generator(
            method='POST',
            path='/submit',
            headers={
                'Content-Encoding': 'gzip',
                'Content-Type': 'multipart/form-data; boundary=' + boundary,
            },
            body=data,
        )

        bsp = BreakpadSubmitterResource(config)
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

    def test_existing_uuid(self, datadir, client):
        boundary, data = fetch_payload(datadir, 'socorrofake1_withuuid.raw')

        result = client.post(
            '/submit',
            headers={
                'Content-Type': 'multipart/form-data; boundary=' + boundary,
            },
            body=data
        )
        assert result.status_code == 200

        # Extract the uuid from the response content and verify that it's in
        # the original POST data
        offset = len('CrashID=bp-')
        crash_id = result.content.strip()[offset:]
        crash_id = crash_id.decode('utf-8')
        assert crash_id in str(data)

    # FIXME: test crash report shapes (multiple dumps? no dumps? what else is in there?)
