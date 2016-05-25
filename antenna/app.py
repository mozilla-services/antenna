# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import base64
import json
import logging
from functools import wraps

import falcon

from antenna.configlib import ConfigManager

logger = logging.getLogger('gunicorn.error')


def require_basic_auth(fun):
    """Decorator for requiring HTTP basic auth

    This is used in resources and requires the resource to have
    ``is_valid_auth`` implemented.

    Example::

        class HealthCheckResource:
            def is_valid_auth(self, username, password):
                return (username, password) == ('foo', 'bar')

            @require_basic_auth
            def on_get(self, req, resp):
                ...

    """
    def auth_error():
        raise falcon.HTTPUnauthorized(
            'Authentication required',
            'Authentication required',
            ['Basic']
        )

    @wraps(fun)
    def view_fun(resource, req, resp, *args, **kwargs):
        auth = req.auth
        if not auth:
            auth_error()

        auth = auth.strip()
        parts = auth.split(' ')
        if len(parts) != 2 or parts[0].lower().strip() != 'basic':
            auth_error()

        creds = base64.b64decode(parts[1]).split(':', 1)
        if not resource.is_valid_auth(creds[0], creds[1]):
            auth_error()

        return fun(resource, req, resp, *args, **kwargs)
    return view_fun


class HealthCheckResource(object):
    def __init__(self, config):
        self.username = config('USERNAME', namespace='healthcheck')
        self.password = config('PASSWORD', namespace='healthcheck')

    def is_valid_auth(self, username, password):
        return (username, password) == (self.username, self.password)

    @require_basic_auth
    def on_get(self, req, resp):
        resp.content_type = 'application/json'

        # FIXME: This should query all the subsystems/components/whatever and
        # provide data from them. We need a registration system or something to
        # facilitate that programmatically.
        #
        # Once we know how everything is doing, we can determine the proper
        # status code. For now, 200 is fine.
        resp.status = falcon.HTTP_200
        resp.data = json.dumps({
            'health': 'v1',
        })


def get_app():
    config = ConfigManager()
    app = falcon.API()
    app.add_route('/api/v1/health', HealthCheckResource(config))
    return app
