# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import contextlib

import sys
from unittest import mock

from everett.manager import ConfigManager
import falcon
from falcon.request import Request
from falcon.testing.helpers import create_environ
from falcon.testing.srmock import StartResponseMock
from falcon.testing.test_case import Result
from py.path import local
import pytest
import wsgiref.validate


# Add the parent parent directory to the sys.path so that it can import the
# antenna code.
sys.path.insert(0, str(local(__file__).dirpath().dirpath().dirpath()))


from antenna import metrics  # noqa
from antenna.app import get_app, setup_logging, setup_metrics  # noqa
from antenna.loggingmock import LoggingMock  # noqa
from antenna.metrics import MetricsMock  # noqa
from antenna.s3mock import S3Mock  # noqa


def pytest_runtest_setup():
    # Make sure we set up logging and metrics to sane default values.
    setup_logging('DEBUG')
    setup_metrics(metrics.LoggingMetrics, ConfigManager.from_dict({}))


def build_app(config=None):
    if config is None:
        config = {}

    # Falcon 1.0 has a global variable that denotes whether it should wrap the
    # wsgi stream or not. Every time we rebuild the app, we should set this to
    # False. If we set it to True, it wraps the stream in a
    # falcon.request_helpers.Body which breaks FieldStorage parsing and then we
    # end up with empty crash reports. If we don't set it at all, then tests fail
    # until a test runs which causes it to flip to False first.
    falcon.request._maybe_wrap_wsgi_stream = False

    return get_app(ConfigManager.from_dict(config))


@pytest.fixture
def request_generator():
    """Returns a Falcon Request generator"""
    def _request_generator(method, path, query_string=None, headers=None,
                           body=None):
        env = create_environ(
            method=method,
            path=path,
            query_string=(query_string or ''),
            headers=headers,
            body=body,
        )
        return Request(env)

    return _request_generator


class Client:
    """Test client to ease testing with the Antenna API

    .. Note::

       Falcon 1.0 has test infrastructure that's interesting, but is
       unittest-based and does some weird things that I found difficult to work
       around. A future version of Falcon will have better things so we can
       probably rip all this out when we upgrade.

    """
    def __init__(self, app):
        self.app = app

    def rebuild_app(self, new_config=None):
        """Rebuilds the app

        This is helpful if you've changed configuration and need to rebuild the
        app so that components pick up the new configuration.

        :arg new_config: dict of configuration to build the new app with

        """
        if new_config is None:
            new_config = {}
        self.app = build_app(new_config)

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
        bsr = self.app.get_resource_by_name('breakpad')
        bsr.join_pool()

    def get(self, path, headers=None, **kwargs):
        return self._request('GET', path=path, headers=headers, **kwargs)

    def post(self, path, headers=None, body=None, **kwargs):
        return self._request('POST', path=path, headers=headers, body=body, **kwargs)

    def _request(self, method, path, query_string=None, headers=None,
                 body=None, **kwargs):
        env = create_environ(
            method=method,
            path=path,
            query_string=(query_string or ''),
            headers=headers,
            body=body,
        )

        resp = StartResponseMock()
        # Wrap the app in a validator which will raise an assertion error if
        # either side isn't speaking valid WSGI.
        validator = wsgiref.validate.validator(self.app)
        iterable = validator(env, resp)

        result = Result(iterable, resp.status, resp.headers)

        return result


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
    return Client(build_app())


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
