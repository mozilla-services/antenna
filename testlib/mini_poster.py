# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""This is a rewritten Python-3 compatible multi-part/form-data encoder heavily
inspired by poster <https://bitbucket.org/chrisatlee/poster>.

The API is similar, but the implementation consists of just the bits that we
wanted in Antenna.

Further, this module can be executed::

    python -m testlib.mini_poster [URL]

This will send a minimal fake crash to the specified URL or
``http://localhost:8000/submit``.

"""

import argparse
from email.header import Header
import gzip
import json
import io
import logging
import uuid
import sys

import requests
import six


def _log_everything():
    # Set up all the debug logging for grossest possible output
    from http.client import HTTPConnection
    HTTPConnection.debuglevel = 1

    logging.getLogger('requests').setLevel(logging.DEBUG)
    logging.getLogger('requests.packages.urllib3').setLevel(logging.DEBUG)


def assemble_crash_payload(raw_crash, dumps):
    crash_data = dict(raw_crash)

    if dumps:
        for name, contents in dumps.items():
            if isinstance(contents, six.text_type):
                contents = contents.encode('utf-8')
            elif isinstance(contents, six.binary_type):
                contents = contents
            else:
                contents = six.text_type(contents).encode('utf-8')
            crash_data[name] = ('fakecrash.dump', io.BytesIO(contents))
    return crash_data


def compress(multipart):
    """Takes a multi-part/form-data payload and compresses it

    :arg multipart: a bytes object representing a multi-part/form-data

    :returns: bytes compressed

    """
    bio = io.BytesIO()
    g = gzip.GzipFile(fileobj=bio, mode='w')
    g.write(multipart)
    g.close()
    return bio.getbuffer()


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

        if isinstance(val, (float, int, str)):
            block.append('Content-Disposition: form-data; name="%s"' % Header(key).encode())
            block.append('Content-Type: text/plain; charset=utf-8')
        elif isinstance(val, tuple):
            block.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (
                (Header(key).encode(), Header(val[0]).encode())))
            block.append('Content-Type: application/octet-stream')
        else:
            print('Skipping %r %r' % key)
            continue

        block.append('')
        block.append('')

        output.write('\r\n'.join(block).encode('utf-8'))

        if isinstance(val, str):
            output.write(val.encode('utf-8'))
        elif isinstance(val, (float, int)):
            output.write(str(val).encode('utf-8'))
        else:
            output.write(val[1].read())

        output.write(b'\r\n')

    # Add end boundary and convert to bytes.
    output.write(('--%s--\r\n' % boundary).encode('utf-8'))
    output = output.getvalue()

    headers['Content-Length'] = str(len(output))

    return output, headers


def post_crash(url, crash_payload, compressed=False):
    """Posts a crash to specified url

    .. Note:: This is not full-featured. It's for testing purposes only.

    :arg str url: The url to post to.
    :arg dict crash_payload: The raw crash and dumps as a single thing.
    :arg bool compressed: Whether or not to post a compressed payload.

    :returns: The requests Response instance.

    """
    payload, headers = multipart_encode(crash_payload)

    if compressed:
        payload = compress(payload)
        headers['Content-Encoding'] = 'gzip'

    return requests.post(
        url,
        headers=headers,
        data=payload
    )


def cmdline(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--url', dest='url', default='http://localhost:8000/submit')
    parser.add_argument('--compressed', dest='compressed', action='store_true')
    parser.add_argument('--raw_crash', dest='raw_crash', default='')
    parser.add_argument(
        '--dump', dest='dumps', action='append',
        help=(
            'This is in name:path form. You can have multple dumps, but they have to '
            'have different names.'
        )
    )
    parser.add_argument('--verbose', dest='verbose', action='store_true')
    parsed = parser.parse_args(args)

    print('URL:         %s' % parsed.url)
    print('Compressed?: %s' % parsed.compressed)
    print('Verbose?:    %s' % parsed.verbose)

    logging.basicConfig(level=logging.DEBUG)
    if parsed.verbose:
        _log_everything()

    url = parsed.url
    compressed = parsed.compressed

    if parsed.raw_crash:
        print('Using raw crash %s...' % parsed.raw_crash)
        raw_crash = json.load(open(parsed.raw_crash, 'r'))

        # Remove this if it's there--it gets generated by the collector
        if 'dump_checksums' in raw_crash:
            del raw_crash['dump_checksums']

        # FIXME(willkg): Should we remove other things, too?

    else:
        print('Generating crash...')
        # FIXME(willkg): Generate a crash here
        raw_crash = {'ProductName': 'Firefox', 'Version': '1'}

    dumps = {}
    if parsed.dumps:
        for dump in parsed.dumps:
            if ':' in dump:
                # This is name:path form
                dump_name, dump_path = dump.split(':')
            else:
                dump_name, dump_path = 'upload_file_minidump', dump

            print('Adding dump %s -> %s...' % (dump_name, dump_path))
            dumps[dump_name] = open(dump_path, 'rb').read()

    print('Assembling payload...')
    crash_payload = assemble_crash_payload(
        raw_crash=raw_crash,
        dumps=dumps
    )

    if compressed:
        print('Posting compressed crash report...')
    else:
        print('Posting uncompressed crash report...')
    resp = post_crash(
        url=url,
        crash_payload=crash_payload,
        compressed=compressed
    )

    print('Post response: %s %r' % (resp.status_code, resp.content))
    return 0


if __name__ == '__main__':
    sys.exit(cmdline(sys.argv[1:]))
