# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os

import pytest
import requests

from testlib import mini_poster


logger = logging.getLogger(__name__)


class Test20mbLimit:
    """Post a crash that's too big--it should be rejected"""
    def _test_crash_size(self, posturl, size, crash_generator):
        raw_crash, dumps = crash_generator.generate()

        dumps['upload_file_minidump'] = ''

        crash_payload = mini_poster.assemble_crash_payload(raw_crash, dumps)
        payload, headers = mini_poster.multipart_encode(crash_payload)
        base_size = len(payload)

        # Create a "dump file" which is really just a bunch of 'a' such that
        # the entire payload is equal to size
        dumps['upload_file_minidump'] = 'a' * (size - base_size)

        crash_payload = mini_poster.assemble_crash_payload(raw_crash, dumps)
        payload, headers = mini_poster.multipart_encode(crash_payload)

        if len(payload) != size:
            raise ValueError('payload size %s', len(payload))

        try:
            resp = requests.post(posturl, headers=headers, data=payload)
            return resp.status_code

        except requests.exceptions.ConnectionError as exc:
            # NOTE(willkg): requests uses httplib which raises an exception if
            # the connection is closed, but doesn't read the HTTP response that
            # might be there. Thus requests never gets the HTTP response.
            #
            # So the best we can test for at this time without a ton of work is
            # to make sure we get a ConnectionError with a broken pipe.
            #
            # https://github.com/kennethreitz/requests/issues/2422
            if 'Broken pipe' in str(exc):
                # Treating this as a 413
                return 413
            raise

        return 200

    @pytest.mark.skipif(
        bool(os.environ.get('NONGINX')),
        reason=(
            'Requires nginx which you probably do not have running '
            'via localhost'
        ))
    @pytest.mark.parametrize('size, status_code', [
        # up to and including 20mb should get an HTTP 200
        ((20 * 1024 * 1024) - 1, 200),
        ((20 * 1024 * 1024), 200),

        # past 20mb, so this should fail with an HTTP 413
        ((20 * 1024 * 1024) + 1, 413)
    ])
    def test_crash_size(self, posturl, size, status_code, crash_generator):
        # mini_poster._log_everything()
        result = self._test_crash_size(posturl, size, crash_generator)
        assert result == status_code
