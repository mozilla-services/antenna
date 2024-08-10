# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import json


class TestHealthChecks:
    def test_no_version(self, client, tmpdir):
        # Set basedir here to tmpdir which we *know* doesn't have a
        # version.json in it.
        client.rebuild_app({"BASEDIR": str(tmpdir)})

        result = client.simulate_get("/__version__")
        assert json.loads(result.content) == {}

    def test_version(self, client, tmpdir):
        client.rebuild_app({"BASEDIR": str(tmpdir)})

        # NOTE(willkg): The actual version.json has other things in it,
        # but our endpoint just spits out the file verbatim, so we
        # can test with whatever.
        version_path = tmpdir.join("/version.json")
        version_path.write('{"commit": "ou812"}')

        result = client.simulate_get("/__version__")
        version_info = {"commit": "ou812"}
        assert json.loads(result.content) == version_info

    def test_lb_heartbeat(self, client):
        resp = client.simulate_get("/__lbheartbeat__")
        assert resp.status_code == 200

    def test_heartbeat(self, client):
        resp = client.simulate_get("/__heartbeat__")
        assert resp.status_code == 200
        # NOTE(willkg): This isn't mocked out, so it's entirely likely that
        # this expected result will change over time.
        assert resp.json == {"errors": []}

    def test_broken(self, client):
        resp = client.simulate_get("/__broken__")
        assert resp.status_code == 500

        # FIXME(willkg): It would be great to verify that an error got to fakesentry,
        # but simulate_get() is faking the middleware so sentry-sdk never sends an
        # error. Falcon doesn't have a LiveServerTestCase (Django) equivalent. I'm not
        # sure how else we can effectively test integration with sentry-sdk without
        # mocking a bunch of stuff.
