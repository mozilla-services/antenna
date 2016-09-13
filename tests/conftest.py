# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import pytest
import sys

from everett.manager import ConfigManager
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
