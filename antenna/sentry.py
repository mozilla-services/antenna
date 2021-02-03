# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Module holding Sentry-related functions.

Infrastructure for optionally wrapping things in Sentry contexts to capture
unhandled exceptions.
"""

import logging
import sys

from raven import Client
from raven.conf import setup_logging
from raven.handlers.logging import SentryHandler
from raven.middleware import Sentry

from antenna.util import get_version_info


logger = logging.getLogger(__name__)

# Global Sentry client singleton
_sentry_client = None


def setup_sentry_logging():
    """Set up sentry logging of exceptions."""
    if _sentry_client:
        setup_logging(SentryHandler(_sentry_client))


def set_sentry_client(sentry_dsn, basedir):
    """Set a Sentry client using a given sentry_dsn.

    To clear the client, pass in something falsey like ``''`` or ``None``.

    """
    global _sentry_client
    if sentry_dsn:
        version_info = get_version_info(basedir)
        commit = version_info.get("commit")[:8]

        _sentry_client = Client(
            dsn=sentry_dsn, include_paths=["antenna"], tags={"commit": commit}
        )
        logger.info("Set up sentry client")
    else:
        _sentry_client = None
        logger.info("Removed sentry client")


class WSGILoggingMiddleware:
    """WSGI middleware that logs unhandled exceptions."""

    def __init__(self, application):
        # NOTE(willkg): This has to match how the Sentry middleware works so
        # that we can (ab)use that fact and access the underlying application.
        self.application = application

    def __call__(self, environ, start_response):
        """Wrap application in exception capture code."""
        try:
            return self.application(environ, start_response)

        except Exception:
            logger.exception("Unhandled exception")
            exc_info = sys.exc_info()
            start_response(
                "500 Internal Server Error",
                [("content-type", "application/json; charset=utf-8")],
                exc_info,
            )
            return [b'{"msg": "COUGH! Internal Server Error"}']


def wsgi_capture_exceptions(app):
    """Wrap a WSGI app with some kind of unhandled exception capture.

    If a Sentry client is configured, then this will send unhandled exceptions
    to Sentry. Otherwise, it will send them as part of the middleware.

    """
    if _sentry_client is None:
        return WSGILoggingMiddleware(app)
    else:
        return Sentry(app, _sentry_client)
