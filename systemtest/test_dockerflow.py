# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging

import requests


LOGGER = logging.getLogger(__name__)


class TestDockerflow:
    def test_version(self, baseurl):
        resp = requests.get(baseurl + "__version__", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        data_keys = list(sorted(data.keys()))
        # It's got "cloud" in the local dev environment and 5 keys in a server
        # environment
        assert data_keys == ["cloud"] or data_keys == [
            "build",
            "cloud",
            "commit",
            "source",
            "version",
        ]

    def test_heartbeat(self, baseurl):
        resp = requests.get(baseurl + "__heartbeat__", timeout=5)
        assert resp.status_code == 200

    def test_lbheartbeat(self, baseurl):
        resp = requests.get(baseurl + "__lbheartbeat__", timeout=5)
        assert resp.status_code == 200
