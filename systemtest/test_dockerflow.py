# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging

import requests


LOGGER = logging.getLogger(__name__)


class TestDockerflow:
    def test_version(self, baseurl):
        resp = requests.get(baseurl + "__version__")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_heartbeat(self, baseurl):
        resp = requests.get(baseurl + "__heartbeat__")
        assert resp.status_code == 200

    def test_lbheartbeat(self, baseurl):
        resp = requests.get(baseurl + "__lbheartbeat__")
        assert resp.status_code == 200
