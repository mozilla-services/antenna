# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from http.client import HTTPConnection, HTTPSConnection, RemoteDisconnected
from contextlib import contextmanager
import logging
import urllib

import pytest

from testlib import mini_poster


logger = logging.getLogger(__name__)


@contextmanager
def http_post(posturl, headers, data):
    parsed = urllib.parse.urlparse(posturl)
    if ":" in parsed.netloc:
        host, port = parsed.netloc.split(":")
    else:
        host = parsed.netloc
        port = "443" if posturl.startswith("https") else "80"

    if posturl.startswith("https"):
        conn = HTTPSConnection(host, int(port), timeout=120)
    else:
        conn = HTTPConnection(host, int(port), timeout=120)
    conn.request("POST", parsed.path, headers=headers, body=data)
    try:
        yield conn.getresponse()
    finally:
        conn.close()


class TestContentLength:
    def test_no_content_length(self, posturl, crash_generator):
        """Post a crash with no content-length"""
        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        del headers["Content-Length"]

        # Do an HTTP POST with no Content-Length
        with http_post(posturl, headers, payload) as resp:
            assert resp.getcode() == 200
            assert str(resp.read(), encoding="utf-8").startswith("CrashID=")

    def test_content_length_0(self, posturl, crash_generator):
        """Post a crash with a content-length 0"""
        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        # Add wrong content-length
        headers["Content-Length"] = "0"

        with http_post(posturl, headers, payload) as resp:
            assert resp.getcode() == 400
            assert (
                str(resp.read(), encoding="utf-8")
                == "Discarded=malformed_no_content_length"
            )

    def test_content_length_20(self, posturl, crash_generator):
        """Post a crash with a content-length 20 which is less than content"""
        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        assert int(headers["Content-Length"]) > 20

        # Add wrong content-length
        headers["Content-Length"] = "20"

        with http_post(posturl, headers, payload) as resp:
            assert resp.getcode() == 400
            assert (
                str(resp.read(), encoding="utf-8")
                == "Discarded=malformed_invalid_payload_structure"
            )

    def test_content_length_1000(self, posturl, crash_generator, nginx):
        """Post a crash with a content-length greater than size of payload."""
        if not nginx:
            pytest.skip("test requires nginx")

        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        # Add wrong content-length
        headers["Content-Length"] = "1000"

        try:
            with http_post(posturl, headers, payload) as resp:
                status_code = resp.getcode()
        except RemoteDisconnected:
            # If there's an ELB and nginx times out waiting for the rest of the
            # request, then we get an HTTP 504. If there's no ELB (we're
            # connecting directly to nginx), then nginx just drops the
            # connection and we get back a RemoteDisconnected error.
            status_code = 504

        # Verify we get an HTTP 504 because something timed out waiting for the
        # HTTP client (us) to send the rest of the data which is expected
        # because we sent a bad content-length
        assert status_code == 504

    def test_content_length_non_int(self, posturl, crash_generator):
        """Post a crash with a content-length that isn't an int"""
        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        # Add wrong content-length
        headers["Content-Length"] = "foo"

        with http_post(posturl, headers, payload) as resp:
            assert resp.getcode() == 400
