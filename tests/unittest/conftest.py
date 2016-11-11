# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import contextlib
from pathlib import Path
import sys
from unittest import mock

from everett.manager import ConfigManager
from falcon.request import Request
from falcon.testing.helpers import create_environ
from falcon.testing.client import TestClient
import pytest


# Add repository root so we can import Antenna.
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Add testlib so we can import testlib modules.
sys.path.insert(0, str(REPO_ROOT / 'tests'))

from antenna import metrics  # noqa
from antenna.app import get_app, setup_logging, setup_metrics  # noqa
from antenna.metrics import MetricsMock  # noqa
from testlib.loggingmock import LoggingMock  # noqa
from testlib.s3mock import S3Mock  # noqa


def pytest_runtest_setup():
    # Make sure we set up logging and metrics to sane default values.
    setup_logging('DEBUG')
    setup_metrics(metrics.LoggingMetrics, ConfigManager.from_dict({}))


@pytest.fixture
def request_generator():
    """Returns a Falcon Request generator"""
    def _request_generator(method, path, query_string=None, headers=None, body=None):
        env = create_environ(
            method=method,
            path=path,
            query_string=(query_string or ''),
            headers=headers,
            body=body,
        )
        return Request(env)

    return _request_generator


class AntennaTestClient(TestClient):
    """Test client to ease testing with Antenna API"""
    def rebuild_app(self, new_config=None):
        """Rebuilds the app

        This is helpful if you've changed configuration and need to rebuild the
        app so that components pick up the new configuration.

        :arg new_config: dict of configuration to build the new app with

        """
        if new_config is None:
            new_config = {}
        self.app = get_app(ConfigManager.from_dict(new_config))

    def join_app(self):
        """This goes through and calls join on all gevent pools in the app

        Call this after doing a ``.get()`` or ``.post()`` to force all post
        processing to occur before this returns.

        For example::

            resp = client.get(...)
            client.join_app()

            assert resp.status_code == 200

        """
        # FIXME(willkg): This is hard-coded for now. We can fix that later if
        # we add other pools to the system.
        bsr = self.get_resource_by_name('breakpad')
        bsr.join_pool()

    def get_resource_by_name(self, name):
        """Retrieves the Falcon API resource by name"""
        # NOTE(willkg): The "app" here is a middleware which should have an
        # .application attribute which is the actual AntennaAPI that we want.
        return self.app.application.get_resource_by_name(name)


@pytest.fixture
def client():
    """Test client for the Antenna API

    This creates an app and a test client that uses that app to submit HTTP
    GET/POST requests.

    If you need it to use an app with a different configuration, you can
    rebuild the app::

        def test_foo(client, tmpdir):
            client.rebuild_app({
                'BASEDIR': str(tmpdir)
            })

    """
    return AntennaTestClient(get_app(ConfigManager.from_dict({})))


@pytest.yield_fixture
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
def loggingmock():
    """Returns a loggingmock that builds a logging mock context to record logged records

    Usage::

        def test_something(loggingmock):
            with loggingmock() as lm:
                # do stuff
                assert lm.has_record(
                    name='foo.bar',
                    level=logging.INFO,
                    msg_contains='some substring'
                )


    You can specify names, too::

        def test_something(loggingmock):
            with loggingmock(['antenna', 'botocore']) as lm:
                # do stuff
                assert lm.has_record(
                    name='foo.bar',
                    level=logging.INFO,
                    msg_contains='some substring'
                )

    """
    @contextlib.contextmanager
    def _loggingmock(names=None):
        with LoggingMock(names=names) as loggingmock:
            yield loggingmock
    return _loggingmock


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
        with mock.patch('random.random') as mock_random:
            mock_random.return_value = value
            yield

    return _randommock
