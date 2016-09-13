# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

from antenna.app import BreakpadSubmitterResource


class TestHealthCheckResource:
    def test_good(self, client):
        result = client.get('/api/v1/health')
        assert result.json['health'] == 'v1'


class TestBreakpadSubmitterResource:
    @pytest.mark.xfail(run=False, reason='write me')
    def test_extract_payload(self, client):
        result = client.post(
            '/submit',
            headers={},
            body=''
        )

        # FIXME: write tests for this; test _process_fieldstorage along with it

    # FIXME: test crash report
    # FIXME: test compressed crash report
    # FIXME: test crash report with uuid
    # FIXME: test crash report shapes (multiple dumps? no dumps? what else is in there?)

    # FIXME: test crashid is returned and content type is correct
