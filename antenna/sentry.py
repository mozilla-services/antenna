# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Infrastructure for optionally wrapping things in Sentry contexts to capture
unhandled exceptions

"""

from contextlib import contextmanager
import logging
import sys

from raven import Client
from raven.middleware import Sentry


logger = logging.getLogger(__name__)

# Global Sentry client singleton
_sentry_client = None


def set_sentry_client(sentry_dsn):
    """Sets a Sentry client using a given sentry_dsn

    To clear the client, pass in something falsey like ``''`` or ``None``.

    """
    global _sentry_client
    if sentry_dsn:
        _sentry_client = Client(dsn=sentry_dsn, include_paths=['antenna'])
        logger.info('Set up sentry client')
    else:
        _sentry_client = None
        logger.info('Removed sentry client')


class WSGILoggingMiddleware(object):
    """WSGI middleware that logs unhandled exceptions"""
    def __init__(self, application):
        # NOTE(willkg): This has to match how the Sentry middleware works so
        # that we can (ab)use that fact and access the underlying application.
        self.application = application

    def __call__(self, environ, start_response):
        try:
            return self.application(environ, start_response)

        except Exception:
            logger.exception('Unhandled exception')
            exc_info = sys.exc_info()
            start_response(
                '500 Internal Server Error',
                [('content-type', 'text/plain')],
                exc_info
            )
            return [b'COUGH! Internal Server Error']


def wsgi_capture_exceptions(app):
    """Wraps a WSGI app with some kind of unhandled exception capture

    If a Sentry client is configured, then this will send unhandled exceptions
    to Sentry. Otherwise, it will send them as part of the middleware.

    """
    if _sentry_client is None:
        return WSGILoggingMiddleware(app)
    else:
        return Sentry(app, _sentry_client)


@contextmanager
def capture_unhandled_exceptions():
    """Context manager for capturing unhandled exceptions

    If a Sentry client is set (see :py:func:`set_sentry_client`), then this
    will capture unhandled exceptions and send the data to Sentry.

    To use::

        with capture_unhandled_exceptions():
            # do crazy things here


    Note: This will re-raise the exception, so it doesn't handle
    exceptions--just captures them.

    """
    try:
        yield

    except Exception:
        if _sentry_client is None:
            logger.warning('No Sentry client set up.')
        else:
            logger.info('Unhandled exception sent to sentry.')
            _sentry_client.captureException()
        raise
