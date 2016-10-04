# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import io

from antenna.mini_poster import multipart_encode


def test_multipart_encode_with_files():
    raw_crash = {
        'ProjectName': 'Test',
        'Version': '1.0',
        # The io.BytesIO is a file-like object, so this will end up as a file.
        'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
    }

    body, headers = multipart_encode(raw_crash, boundary='socorrobound1234567')
    assert headers['Content-Type'] == 'multipart/form-data; boundary=socorrobound1234567'
    assert headers['Content-Length'] == '431'
    assert (
        body ==
        (
            b'--socorrobound1234567\r\n'
            b'Content-Disposition: form-data; name="ProjectName"\r\n'
            b'Content-Type: text/plain; charset=utf-8\r\n'
            b'\r\n'
            b'Test\r\n'
            b'--socorrobound1234567\r\n'
            b'Content-Disposition: form-data; name="Version"\r\n'
            b'Content-Type: text/plain; charset=utf-8\r\n'
            b'\r\n'
            b'1.0\r\n'
            b'--socorrobound1234567\r\n'
            b'Content-Disposition: form-data; name="upload_file_minidump"; filename="fakecrash.dump"\r\n'
            b'Content-Type: application/octet-stream\r\n'
            b'\r\n'
            b'abcd1234\r\n'
            b'--socorrobound1234567--\r\n'
        )
    )
