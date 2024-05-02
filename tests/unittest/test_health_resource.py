# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from contextlib import contextmanager
import json
import os


@contextmanager
def gcs_crashstorage_envvar():
    # NOTE(willkg): we do this in a goofy way here because it means we don't actually
    # have to set this in the environment which causes the app to fail at startup
    # because the bucket doesn't exist
    key = "CRASHMOVER_CRASHSTORAGE_CLASS"
    os.environ[key] = "antenna.ext.gcs.crashstorage.GcsCrashStorage"

    yield

    del os.environ[key]


class TestHealthChecks:
    def test_no_version(self, client, tmpdir):
        # Set basedir here to tmpdir which we *know* doesn't have a
        # version.json in it.
        client.rebuild_app({"BASEDIR": str(tmpdir)})

        result = client.simulate_get("/__version__")
        version_info = {"cloud": "AWS"}
        assert json.loads(result.content) == version_info

    def test_no_version_gcp(self, client, tmpdir):
        # Set basedir here to tmpdir which we *know* doesn't have a
        # version.json in it.
        client.rebuild_app({"BASEDIR": str(tmpdir)})

        with gcs_crashstorage_envvar():
            result = client.simulate_get("/__version__")
        version_info = {"cloud": "GCP"}
        assert json.loads(result.content) == version_info

    def test_version_aws(self, client, tmpdir):
        client.rebuild_app({"BASEDIR": str(tmpdir)})

        # NOTE(willkg): The actual version.json has other things in it,
        # but our endpoint just spits out the file verbatim, so we
        # can test with whatever.
        version_path = tmpdir.join("/version.json")
        version_path.write('{"commit": "ou812"}')

        result = client.simulate_get("/__version__")
        version_info = {"commit": "ou812", "cloud": "AWS"}
        assert json.loads(result.content) == version_info

    def test_version_gcp(self, client, tmpdir):
        client.rebuild_app({"BASEDIR": str(tmpdir)})

        # NOTE(willkg): The actual version.json has other things in it,
        # but our endpoint just spits out the file verbatim, so we
        # can test with whatever.
        version_path = tmpdir.join("/version.json")
        version_path.write('{"commit": "ou812"}')

        with gcs_crashstorage_envvar():
            result = client.simulate_get("/__version__")
        version_info = {"commit": "ou812", "cloud": "GCP"}
        assert json.loads(result.content) == version_info

    def test_lb_heartbeat(self, client):
        resp = client.simulate_get("/__lbheartbeat__")
        assert resp.status_code == 200

    def test_heartbeat(self, client):
        resp = client.simulate_get("/__heartbeat__")
        assert resp.status_code == 200
        # NOTE(willkg): This isn't mocked out, so it's entirely likely that
        # this expected result will change over time.
        assert resp.json == {"errors": [], "info": {}}

    def test_broken(self, client):
        resp = client.simulate_get("/__broken__")
        assert resp.status_code == 500

        # FIXME(willkg): It would be great to verify that an error got to fakesentry,
        # but simulate_get() is faking the middleware so sentry-sdk never sends an
        # error. Falcon doesn't have a LiveServerTestCase (Django) equivalent. I'm not
        # sure how else we can effectively test integration with sentry-sdk without
        # mocking a bunch of stuff.
