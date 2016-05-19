import base64
import json
import logging
from functools import wraps

import falcon

from antenna.configlib import config

logger = logging.getLogger('gunicorn.error')


def require_basic_auth(username, password):
    """Decorator for requiring HTTP basic auth

    :arg username: the valid username to use
    :arg password: the valid password to use

    """
    def auth_error():
        raise falcon.HTTPUnauthorized(
            'Authentication required',
            'Authentication required',
            ['Basic']
        )

    def is_valid(given_username, given_password):
        return (given_username, given_password) == (username, password)

    def decorate(fun):
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
            if not is_valid(creds[0], creds[1]):
                auth_error()

            return fun(resource, req, resp, *args, **kwargs)
        return view_fun
    return decorate


class HealthCheckResource(object):
    @require_basic_auth(
        username=config('USERNAME', namespace='healthcheck'),
        password=config('PASSWORD', namespace='healthcheck'),
    )
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
    app = falcon.API()
    app.add_route('/api/v1/health', HealthCheckResource())
    return app
