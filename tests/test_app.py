# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import base64

import falcon
import pytest

from antenna.app import require_basic_auth


class FakeRequest(object):
    def __init__(self, auth):
        self.auth = auth


def generate_basic_auth_token(username, password):
    token = ':'.join([username, password])
    return 'Basic ' + base64.b64encode(token)


class Test_required_basic_auth:
    class FakeResource(object):
        @require_basic_auth('gooduser', 'goodpwd')
        def on_get(self, req, resp):
            return

    resource = FakeResource()

    def test_no_auth(self):
        # No auth causes it to raise unauthorised
        with pytest.raises(falcon.HTTPUnauthorized):
            self.resource.on_get(FakeRequest(None), None)

    def test_incorrect_auth(self):
        # Incorrect auth scheme causes it to raise unauthorized
        with pytest.raises(falcon.HTTPUnauthorized):
            self.resource.on_get(FakeRequest('Foo'), None)
        with pytest.raises(falcon.HTTPUnauthorized):
            self.resource.on_get(FakeRequest('Foo bar'), None)

    def test_bad_creds(self):
        # Bad auth creds causes it to raise unauthorized
        with pytest.raises(falcon.HTTPUnauthorized):
            token = generate_basic_auth_token('baduser', 'badpwd')
            self.resource.on_get(FakeRequest(token), None)

    def test_good_creds(self):
        token = generate_basic_auth_token('gooduser', 'goodpwd')
        self.resource.on_get(FakeRequest(token), None)


class TestHealthCheckResource:
    def test_no_auth(self, testapp):
        # No auth raises an HTTP 401
        testapp.get('/api/v1/health', status=401)

    def test_bad_auth(self, testapp):
        # Bad auth raises a 401
        testapp.authorization = ('Basic', ('foo', 'bar'))
        testapp.get('/api/v1/health', status=401)

    def test_good(self, testapp):
        # Note: Username and password are in settings_test.ini
        testapp.authorization = ('Basic', ('example', 'examplepw'))
        resp = testapp.get('/api/v1/health')
        assert resp.json['health'] == 'v1'
