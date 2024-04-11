# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import contextlib
import os
from pathlib import Path
import sys
from unittest import mock

import boto3
from botocore.client import ClientError as BotoClientError, Config as BotoConfig
from everett.manager import ConfigManager, ConfigDictEnv, ConfigOSEnv
from falcon.request import Request
from falcon.testing.helpers import create_environ
from falcon.testing.client import TestClient
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage as gcs_storage
from google.cloud.exceptions import NotFound as GCSNotFound
import markus
from markus.testing import MetricsMock
import pytest


# Add repository root so we can import antenna and testlib.
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from antenna.app import get_app, setup_logging  # noqa
from antenna.app import reset_verify_funs  # noqa
from testlib.s3mock import S3Mock  # noqa


def pytest_runtest_setup():
    # Make sure we set up logging and metrics to sane default values.
    setup_logging(logging_level="DEBUG", debug=True, host_id="", processname="antenna")
    markus.configure([{"class": "markus.backends.logging.LoggingMetrics"}])

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
def s3mock():
    """Returns an s3mock context that lets you do S3-related tests

    Usage::

        def test_something(s3mock):
            s3mock.add_step(
                method='PUT',
                url='...'
                resp=s3mock.fake_response(status_code=200)
            )

    """
    with S3Mock() as s3:
        yield s3


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
def s3_client():
    def get_env_var(key):
        return os.environ[f"CRASHMOVER_CRASHSTORAGE_{key}"]

    session = boto3.session.Session(
        aws_access_key_id=get_env_var("ACCESS_KEY"),
        aws_secret_access_key=get_env_var("SECRET_ACCESS_KEY"),
    )
    client = session.client(
        service_name="s3",
        config=BotoConfig(s3={"addressing_style": "path"}),
        endpoint_url=get_env_var("ENDPOINT_URL"),
    )
    return client


@pytest.fixture
def s3_helper(s3_client):
    """Sets up bucket, yields s3_client, and tears down when test is done."""

    def delete_bucket(s3_client, bucket_name):
        resp = s3_client.list_objects(Bucket=bucket_name)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            s3_client.delete_object(Bucket=bucket_name, Key=key)

        # Then delete the bucket
        s3_client.delete_bucket(Bucket=bucket_name)

    # Set up
    bucket_name = os.environ["CRASHMOVER_CRASHSTORAGE_BUCKET_NAME"]
    try:
        delete_bucket(s3_client, bucket_name)
    except BotoClientError:
        s3_client.create_bucket(Bucket=bucket_name)

    yield s3_client

    # Tear down
    delete_bucket(s3_client, bucket_name)


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
