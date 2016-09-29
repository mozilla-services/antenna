# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import gzip
import io

from antenna.app import BreakpadSubmitterResource


class TestHealthVersionResource:
    def test_no_version(self, client, tmpdir):
        # Set basedir here to tmpdir which we *know* doesn't have a
        # version.json in it.
        client.rebuild_app({
            'BASEDIR': str(tmpdir)
        })

        result = client.get('/__version__')
        assert result.content == b'{}'

    def test_version(self, client, tmpdir):
        client.rebuild_app({
            'BASEDIR': str(tmpdir)
        })

        # NOTE(willkg): The actual version.json has other things in it,
        # but our endpoint just spits out the file verbatim, so we
        # can test with whatever.
        version_path = tmpdir.join('/version.json')
        version_path.write('{"commit": "ou812"}')

        result = client.get('/__version__')
        assert result.content == b'{"commit": "ou812"}'


class TestBreakpadSubmitterResource:
    config_vars = {}

    def test_submit_crash_report_reply(self, client, payload_generator):
        boundary, data = payload_generator('socorrofake1.raw')

        result = client.post(
            '/submit',
            headers={
                'Content-Type': 'multipart/form-data; boundary=' + boundary,
            },
            body=data
        )
        assert result.status_code == 200
        assert result.content.startswith(b'CrashID=bp')

    def test_extract_payload(self, config, request_generator,
                             payload_generator):
        boundary, data = payload_generator('socorrofake1.raw')
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

    def test_extract_payload_2_dumps(self, config, request_generator, payload_generator):
        boundary, data = payload_generator('socorrofake2.raw')
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

    def test_extract_payload_compressed(self, config, request_generator, payload_generator):
        boundary, data = payload_generator('socorrofake1.raw')

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

    def test_existing_uuid(self, client, payload_generator):
        boundary, data = payload_generator('socorrofake1_withuuid.raw')

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
