from http.client import HTTPConnection
import logging
import os
import urllib

import pytest

from testlib import mini_poster


logger = logging.getLogger(__name__)


def http_post(posturl, headers, data):
    parsed = urllib.parse.urlparse(posturl)
    host, port = parsed.netloc.split(':')
    if not port:
        port = '80'
    conn = HTTPConnection(host, int(port))
    conn.request('POST', parsed.path, headers=headers, body=data)
    return conn.getresponse()


class TestContentLength:
    def test_no_content_length(self, posturl, crash_generator):
        """Post a crash with no content-length"""
        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        del headers['Content-Length']

        # Do an HTTP POST with no Content-Length
        resp = http_post(posturl, headers, payload)

        assert resp.getcode() == 200
        assert str(resp.read(), encoding='utf-8').startswith('CrashID=')

    def test_content_length_0(self, posturl, crash_generator):
        """Post a crash with a content-length 0"""
        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        # Add wrong content-length
        headers['Content-Length'] = '0'

        resp = http_post(posturl, headers, payload)

        assert resp.getcode() == 200
        assert str(resp.read(), encoding='utf-8') == 'Discarded=1'

    def test_content_length_20(self, posturl, crash_generator):
        """Post a crash with a content-length 20"""
        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        # Add wrong content-length
        headers['Content-Length'] = '20'

        resp = http_post(posturl, headers, payload)

        assert resp.getcode() == 200
        assert str(resp.read(), encoding='utf-8') == 'Discarded=1'

    @pytest.mark.skipif(
        bool(os.environ.get('NONGINX')),
        reason=(
            'Requires nginx which you probably do not have running '
            'via localhost'
        ))
    def test_content_length_1000(self, posturl, crash_generator):
        """Post a crash with a content-length greater than size of payload"""
        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        # Add wrong content-length
        headers['Content-Length'] = '1000'

        resp = http_post(posturl, headers, payload)

        assert resp.getcode() == 200
        assert str(resp.read(), encoding='utf-8') == 'Discarded=1'

    def test_content_length_non_int(self, posturl, crash_generator):
        """Post a crash with a content-length that isn't an int"""
        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        # Add wrong content-length
        headers['Content-Length'] = 'foo'

        resp = http_post(posturl, headers, payload)

        assert resp.getcode() == 400
