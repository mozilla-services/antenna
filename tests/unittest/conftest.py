# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import contextlib
from pathlib import Path
import logging
import sys
from unittest import mock

from everett.manager import ConfigManager, ConfigDictEnv, ConfigOSEnv
from falcon.request import Request
from falcon.testing.helpers import create_environ
from falcon.testing.client import TestClient
import markus
from markus.testing import MetricsMock
import pytest


# Add repository root so we can import antenna and testlib.
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from antenna.app import get_app, setup_logging  # noqa
from antenna.heartbeat import reset_hb_funs  # noqa
from testlib.s3mock import S3Mock  # noqa


def pytest_runtest_setup():
    # Make sure we set up logging and metrics to sane default values.
    setup_logging(logging_level="DEBUG", debug=True, host_id="", processname="antenna")
    markus.configure([{"class": "markus.backends.logging.LoggingMetrics"}])

    # Wipe any registered heartbeat functions
    reset_hb_funs()


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
        self.app = get_app(self.build_config(new_config))

    def get_crashmover(self):
        """Retrieves the crashmover from the AntennaAPI."""
        # NOTE(willkg): The "app" here is a middleware which should have an
        # .application attribute which is the actual AntennaAPI that we want.
        return self.app.application.crashmover

    def get_resource_by_name(self, name):
        """Retrieves the Falcon API resource by name"""
        # NOTE(willkg): The "app" here is a middleware which should have an
        # .application attribute which is the actual AntennaAPI that we want.
        return self.app.application.get_resource_by_name(name)

    def join_app(self):
        """This goes through and calls join on all gevent pools in the app

        Call this after doing a ``.get()`` or ``.post()`` to force all post
        processing to occur before this returns.

        For example::

            resp = client.get(...)
            client.join_app()

        """
        self.get_crashmover().join_pool()


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


@pytest.fixture
def caplogpp(caplog):
    """caplogpp fixes propagation logger values and returns caplog fixture"""
    changed_loggers = []
    for logger in logging.Logger.manager.loggerDict.values():
        if getattr(logger, "propagate", True) is False:
            logger.propagate = True
            changed_loggers.append(logger)

    yield caplog

    for logger in changed_loggers:
        logger.propagate = False
