# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
import requests

from testlib import mini_poster


logger = logging.getLogger(__name__)


class TestDiscarded:
    def test_wrong_boundary(self, posturl, s3conn, crash_generator):
        """Post a crash with a header with wrong boundary marker."""
        raw_crash, dumps = crash_generator.generate()
        payload, headers = mini_poster.multipart_encode(raw_crash)

        # Mangle the header changing the boundary to something wrong
        headers["Content-Type"] = "multipart/form-data; boundary=foo"

        resp = requests.post(posturl, headers=headers, data=payload)

        assert resp.status_code == 400
        assert (
            str(resp.content, encoding="utf-8") == "Discarded=malformed_no_annotations"
        )

    def test_missing_content_type(self, posturl, s3conn, crash_generator):
        """Test crash missing a content-type header is discarded"""
        raw_crash, dumps = crash_generator.generate()
        payload, headers = mini_poster.multipart_encode(raw_crash)

        # Send no Content-Type header
        resp = requests.post(posturl, headers={}, data=payload)

        assert resp.status_code == 400
        assert (
            str(resp.content, encoding="utf-8") == "Discarded=malformed_no_content_type"
        )

    def test_no_payload(self, posturl, s3conn, crash_generator):
        """Test crash with no payload is discarded"""
        raw_crash, dumps = crash_generator.generate()
        payload, headers = mini_poster.multipart_encode(raw_crash)
        # Zero out the content-length because we're sending an empty
        # payload.
        headers["Content-Length"] = "0"

        # Send no payload
        resp = requests.post(posturl, headers=headers, data="")

        assert resp.status_code == 400
        assert (
            str(resp.content, encoding="utf-8")
            == "Discarded=malformed_no_content_length"
        )

    def test_junk_payload(self, posturl, s3conn, crash_generator):
        """Test crash with a junk payload is discarded"""
        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        # Junkify the payload
        payload = "foobarbaz"

        resp = requests.post(posturl, headers=headers, data=payload)

        assert resp.status_code == 400
        assert (
            str(resp.content, encoding="utf-8") == "Discarded=malformed_no_annotations"
        )

    def test_compressed_payload_bad_header(self, posturl, s3conn, crash_generator):
        """Test crash with a compressed payload, but missing header is discarded"""
        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        # Compress the payload, but don't set the header
        payload = mini_poster.compress(payload)

        resp = requests.post(posturl, headers=headers, data=payload)

        assert resp.status_code == 400
        assert (
            str(resp.content, encoding="utf-8") == "Discarded=malformed_no_annotations"
        )

    def test_compressed_header_non_compressed_payload(
        self, posturl, s3conn, crash_generator
    ):
        """Test crash with a compressed header, but non-compressed payload is discarded"""
        raw_crash, dumps = crash_generator.generate()

        # Generate the payload and headers for a crash with no dumps
        payload, headers = mini_poster.multipart_encode(raw_crash)

        # Add compressed header, but don't compress the payload
        headers["Content-Encoding"] = "gzip"

        resp = requests.post(posturl, headers=headers, data=payload)

        assert resp.status_code == 400
        assert str(resp.content, encoding="utf-8") == "Discarded=malformed_bad_gzip"
