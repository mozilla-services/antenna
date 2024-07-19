# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import contextlib
import os
from pathlib import Path
import sys
from unittest import mock

from everett.manager import ConfigManager, ConfigDictEnv, ConfigOSEnv
from falcon.request import Request
from falcon.testing.helpers import create_environ
from falcon.testing.client import TestClient
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage as gcs_storage
from google.cloud.exceptions import NotFound as GCSNotFound
import markus
from markus.backends import BackendBase
from markus.testing import MetricsMock
import pytest


# Add repository root so we can import antenna and testlib.
REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from antenna.app import get_app, setup_logging  # noqa
from antenna.app import reset_verify_funs  # noqa


class CaptureMetricsUsed(BackendBase):
    """Markus backend for capturing all the metrics that were emitted during tests"""

    def __init__(self, options=None, filters=None):
        self.options = options
        self.filters = filters

    def emit(self, record):
        with open("metrics_emitted.txt", "a") as fp:
            fp.write(f"{record.stat_type}\t{record.key}\t{record.tags!r}\n")


def pytest_runtest_setup():
    # Make sure we set up logging and metrics to sane default values.
    setup_logging(logging_level="DEBUG", debug=True, host_id="", processname="antenna")
    markus.configure(
        [
            {"class": "markus.backends.logging.LoggingMetrics"},
            {"class": CaptureMetricsUsed},
        ]
    )

    # Wipe any registered verify functions
    reset_verify_funs()


@pytest.fixture
def request_generator():
    """Returns a Falcon Request generator"""

    def _request_generator(method, path, query_string=None, headers=None, body=None):
        env = create_environ(
            method=method,
            path=path,
            query_string=(query_string or ""),
            headers=headers,
            body=body,
        )
        return Request(env)

    return _request_generator


class AntennaTestClient(TestClient):
    """Test client to ease testing with Antenna API"""

    @classmethod
    def build_config(cls, new_config=None):
        """Build ConfigManager using environment and overrides."""
        new_config = new_config or {}
        config_manager = ConfigManager(
            environments=[ConfigDictEnv(new_config), ConfigOSEnv()]
        )
        return config_manager

    def rebuild_app(self, new_config):
        """Rebuilds the app

        This is helpful if you've changed configuration and need to rebuild the
        app so that components pick up the new configuration.

        :arg new_config: dict of configuration to override normal values to build the
            new app with

        """
        # Drop all the existing verify functions
        reset_verify_funs()

        # Build the new app
        self.app = get_app(self.build_config(new_config))

    def get_crashmover(self):
        """Retrieves the crashmover from the AntennaApp."""
        return self.app.app.crashmover

    def get_resource_by_name(self, name):
        """Retrieves the Falcon API resource by name"""
        return self.app.app.get_resource_by_name(name)


@pytest.fixture
def client():
    """Test client for the Antenna API

    This creates an app and a test client that uses that app to submit HTTP
    GET/POST requests.

    The app that's created uses configuration defaults. If you need it to use
    an app with a different configuration, you can rebuild the app with
    different configuration::

        def test_foo(client, tmpdir):
            client.rebuild_app({
                'BASEDIR': str(tmpdir)
            })

    """
    return AntennaTestClient(get_app(AntennaTestClient.build_config()))


@pytest.fixture
def gcs_client():
    if os.environ.get("STORAGE_EMULATOR_HOST"):
        client = gcs_storage.Client(
            credentials=AnonymousCredentials(),
            project="test",
        )
        try:
            yield client
        finally:
            for bucket in client.list_buckets():
                try:
                    bucket.delete(force=True)
                except GCSNotFound:
                    pass  # same difference
    else:
        pytest.skip("requires gcs emulator")


@pytest.fixture
def gcs_helper(gcs_client):
    """Sets up bucket, yields gcs_client, and tears down after test is done."""
    # Set up
    bucket_name = os.environ["CRASHMOVER_CRASHSTORAGE_BUCKET_NAME"]
    try:
        gcs_client.get_bucket(bucket_name).delete(force=True)
    except GCSNotFound:
        pass  # same difference
    gcs_client.create_bucket(bucket_name)

    yield gcs_client

    # Tear down
    gcs_client.get_bucket(bucket_name).delete(force=True)


@pytest.fixture
def metricsmock():
    """Returns MetricsMock that a context to record metrics records

    Usage::

        def test_something(metricsmock):
            with metricsmock as mm:
                # do stuff
                assert mm.has_record(
                    stat='some.stat',
                    kwargs_contains={
                        'something': 1
                    }
                )

    """
    return MetricsMock()


@pytest.fixture
def randommock():
    """Returns a contextmanager that mocks random.random() at a specific value

    Usage::

        def test_something(randommock):
            with randommock(0.55):
                # test stuff...

    """

    @contextlib.contextmanager
    def _randommock(value):
        with mock.patch("random.random") as mock_random:
            mock_random.return_value = value
            yield

    return _randommock
