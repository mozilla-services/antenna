# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import pytest
import sys

from everett.manager import ConfigManager, ConfigDictEnv
from falcon.request import Request, RequestOptions
from falcon.testing.helpers import create_environ
from falcon.testing.srmock import StartResponseMock
from falcon.testing.test_case import Result
import wsgiref.validate

# Add the parent directory to the sys.path so that it can import the antenna
# code.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


from antenna.app import get_app  # noqa


@pytest.fixture
def app():
    return get_app(ConfigManager([]))


@pytest.fixture
def config(request):
    """Returns a ConfigManager instance primed with config vars

    Specify the config vars you want it primed with on the class. For example::

        class TestFoo:
            config_vars = {
                'SOME_VAR': 'some_val'
            }

            def test_foo(self, config):
                ...

    """
    return ConfigManager([ConfigDictEnv(dict(request.cls.config_vars))])


@pytest.fixture
def request_generator():
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

    def get(self, path, headers=None, **kwargs):
        return self._request(
            'GET', path=path, headers=headers, **kwargs
        )

    def post(self, path, headers=None, body=None, **kwargs):
        return self._request(
            'POST', path=path, headers=headers, body=body, **kwargs
        )

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
        validator = wsgiref.validate.validator(self.app)
        iterable = validator(env, resp)

        result = Result(iterable, resp.status, resp.headers)

        return result


@pytest.fixture
def client(app):
    """Test client for the Antenna API"""
    return Client(app)


@pytest.fixture
def datadir():
    return os.path.join(os.path.dirname(__file__), 'data')
