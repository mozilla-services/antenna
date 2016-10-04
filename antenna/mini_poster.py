# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""This is a rewritten Python-3 compatible multi-part/form-data encoder heavily
inspired by poster <https://bitbucket.org/chrisatlee/poster>.

The API is similar, but the implementation consists of just the bits that we
wanted in Antenna.

"""

from email.header import Header
import io
import uuid


def multipart_encode(raw_crash, boundary=None):
    """Takes a raw_crash as a Python dict and converts to a multipart/form-data

    Here's an example ``raw_crash``::

        {
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        }

    You can also pass in file pointers for files::

        {
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', open('crash.dmp', 'rb'))
        }


    This returns a tuple of two things:

    1. a ``bytes`` object with the HTTP POST payload
    2. a dict of headers with ``Content-Type`` and ``Content-Length`` in it


    :arg params: Python dict of name -> value pairs. Values must be either
         strings or a tuple of (filename, file-like objects with ``.read()``).

    :arg boundary: The MIME boundary string to use. Otherwise this will be
        generated.

    :returns: tuple of (bytes, headers dict)

    """
    if boundary is None:
        boundary = uuid.uuid4().hex

    output = io.BytesIO()
    headers = {
        'Content-Type': 'multipart/form-data; boundary=%s' % boundary,
    }

    for key, val in sorted(raw_crash.items()):
        block = [
            '--%s' % boundary
        ]

        if isinstance(val, str):
            block.append('Content-Disposition: form-data; name="%s"' % Header(key).encode())
            block.append('Content-Type: text/plain; charset=utf-8')
        else:
            block.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (
                (Header(key).encode(), Header(val[0]).encode())))
            block.append('Content-Type: application/octet-stream')

        block.append('')
        block.append('')

        output.write('\r\n'.join(block).encode('utf-8'))

        if isinstance(val, str):
            output.write(val.encode('utf-8'))
        else:
            output.write(val[1].read())

        output.write(b'\r\n')

    # Add end boundary and convert to bytes.
    output.write(('--%s--\r\n' % boundary).encode('utf-8'))
    output = output.getvalue()

    headers['Content-Length'] = str(len(output))

    return output, headers
