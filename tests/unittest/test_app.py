# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import io

from everett.manager import ConfigManager

from antenna.app import BreakpadSubmitterResource
from antenna.mini_poster import multipart_encode
from antenna.util import compress


class TestBasic:
    def test_404(self, client):
        result = client.get('/foo')
        assert result.status_code == 404

    def test_home_page(self, client):
        result = client.get('/')
        assert result.status_code == 200


class TestHealthChecks:
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

    def test_lb_heartbeat(self, client):
        resp = client.get('/__lbheartbeat__')
        assert resp.status_code == 200

    def test_heartbeat(self, client):
        resp = client.get('/__heartbeat__')
        assert resp.status_code == 200
        # NOTE(willkg): This isn't mocked out, so it's entirely likely that
        # this expected result will change over time.
        assert (
            resp.content ==
            b'{"errors": [], "info": {"BreakpadSubmitterResource.queue_size": 0}}'
        )


class TestBreakpadSubmitterResource:
    empty_config = ConfigManager.from_dict({})

    def test_submit_crash_report_reply(self, client):
        data, headers = multipart_encode({
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        })

        result = client.post(
            '/submit',
            headers=headers,
            body=data,
        )
        assert result.status_code == 200
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

    def test_existing_uuid(self, client):
        data, headers = multipart_encode({
            'uuid': 'de1bb258-cbbf-4589-a673-34f800160918',
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        })

        result = client.post(
            '/submit',
            headers=headers,
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
