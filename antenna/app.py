# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os
import logging.config
from pathlib import Path
import sys

from everett.manager import ConfigManager, ConfigEnvFileEnv, ConfigOSEnv, parse_class
from everett.component import ConfigOptions, RequiredConfigMixin
import falcon
from raven import Client
from raven.middleware import Sentry

from antenna import metrics
from antenna.breakpad_resource import BreakpadSubmitterResource
from antenna.health_resource import (
    BrokenResource,
    HeartbeatResource,
    LBHeartbeatResource,
    VersionResource,
)


logger = logging.getLogger(__name__)
mymetrics = metrics.get_metrics(__name__)


def setup_logging(logging_level):
    """Initializes Python logging configuration"""
    dc = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'development': {
                'format': '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S %z',
            },
        },
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'development',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
        'loggers': {
            'antenna': {
                'propagate': False,
                'handlers': ['console'],
                'level': logging_level,
            },
        },
    }
    logging.config.dictConfig(dc)


def setup_metrics(metrics_class, config):
    """Initializes the metrics system"""
    logger.info('Setting up metrics: %s', metrics_class)
    metrics.metrics_configure(metrics_class, config)


def log_config(logger, component):
    for namespace, key, val, opt in component.get_runtime_config():
        if namespace:
            namespaced_key = '%s_%s' % ('_'.join(namespace), key)
        else:
            namespaced_key = key

        namespaced_key = namespaced_key.upper()

        if 'secret' in opt.key.lower():
            msg = '%s=*****' % namespaced_key
        else:
            msg = '%s=%s' % (namespaced_key, val)
        logger.info(msg)


class AppConfig(RequiredConfigMixin):
    """Application-level config

    To pull out a config item, you can do this::

        config = ConfigManager([ConfigOSEnv()])
        app_config = AppConfig(config)

        debug = app_config('debug')


    To create a component with configuration, you can do this::

        class SomeComponent(RequiredConfigMixin):
            required_config = ConfigOptions()

            def __init__(self, config):
                self.config = config.with_options(self)

        some_component = SomeComponent(app_config.config)


    To pass application-level configuration to components, you should do it
    through arguments like this::

        class SomeComponent(RequiredConfigMixin):
            required_config = ConfigOptions()

            def __init__(self, config, debug):
                self.config = config.with_options(self)
                self.debug = debug

        some_component = SomeComponent(app_config.config_manager, debug)

    """
    required_config = ConfigOptions()
    required_config.add_option(
        'basedir',
        default=str(Path(__file__).parent.parent),
        doc='The root directory for this application to find and store things.'
    )
    required_config.add_option(
        'logging_level',
        default='DEBUG',
        doc='The logging level to use. DEBUG, INFO, WARNING, ERROR or CRITICAL'
    )
    required_config.add_option(
        'metrics_class',
        default='antenna.metrics.LoggingMetrics',
        doc='Metrics client to use',
        parser=parse_class
    )
    required_config.add_option(
        'secret_sentry_dsn',
        default='',
        doc=(
            'Sentry DSN to use. See https://docs.sentry.io/quickstart/#configure-the-dsn '
            'for details. If this is not set an unhandled exception logging middleware '
            'will be used instead.'
        )
    )

    def __init__(self, config):
        self.config_manager = config
        self.config = config.with_options(self)

    def __call__(self, key):
        return self.config(key)


class HomePageResource:
    """Shows something at /"""
    def __init__(self, config):
        pass

    def on_get(self, req, resp):
        resp.content_type = 'text/html'
        resp.status = falcon.HTTP_200
        resp.body = '<html><body><p>I am Antenna.</p></body></html>'


class AntennaAPI(falcon.API):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._all_resources = {}

    def add_route(self, name, uri_template, resource, *args, **kwargs):
        """Adds specified Falcon route

        :arg str name: friendly name for this route; use alphanumeric characters

        :arg str url_template: Falcon url template for this route

        :arg obj resource: Falcon resource to handl this route

        """
        self._all_resources[name] = resource
        super().add_route(uri_template, resource, *args, **kwargs)

    def get_resource_by_name(self, name):
        """Returns the registered resource with specified name

        :arg str name: the name of the resource to get

        :raises KeyError: if there is no resource by that name

        """
        return self._all_resources[name]

    def get_resources(self):
        """Returns a list of registered resources"""
        return self._all_resources.values()

    def get_runtime_config(self, namespace=None):
        for res in self.get_resources():
            if hasattr(res, 'get_runtime_config'):
                for item in res.get_runtime_config(namespace):
                    yield item


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


def get_app(config=None):
    """Returns AntennaAPI instance"""
    try:
        if config is None:
            config = ConfigManager(
                environments=[
                    # Pull configuration from env file specified as ANTENNA_ENV
                    ConfigEnvFileEnv([os.environ.get('ANTENNA_ENV')]),
                    # Pull configuration from environment variables
                    ConfigOSEnv()
                ],
                doc=(
                    'For configuration help, see '
                    'https://antenna.readthedocs.io/en/latest/configuration.html'
                )
            )

        app_config = AppConfig(config)

        # Build a Sentry client if we're so configured
        if app_config('secret_sentry_dsn'):
            sentry_client = Client(
                dsn=app_config('secret_sentry_dsn'),
                include_paths=['antenna'],
            )
        else:
            sentry_client = None

        try:
            setup_logging(app_config('logging_level'))
            setup_metrics(app_config('metrics_class'), config)

            log_config(logger, app_config)
            # FIXME(willkg): This is a little gross, but it's a component and
            # we want to log the configuration, but it's "internal" to the
            # metrics module.
            log_config(logger, metrics._metrics_impl)

            app = AntennaAPI(config)

            app.add_route('homepage', '/', HomePageResource(config))
            app.add_route('breakpad', '/submit', BreakpadSubmitterResource(config))
            app.add_route('version', '/__version__', VersionResource(config, basedir=app_config('basedir')))
            app.add_route('heartbeat', '/__heartbeat__', HeartbeatResource(config, app))
            app.add_route('lbheartbeat', '/__lbheartbeat__', LBHeartbeatResource(config))
            app.add_route('broken', '/__broken__', BrokenResource(config))

            log_config(logger, app)

        except Exception:
            if sentry_client:
                sentry_client.captureException()
            raise

        # Wrap the app in some kind of unhandled exception notification mechanism
        if sentry_client:
            app = Sentry(app, sentry_client)
        else:
            app = WSGILoggingMiddleware(app)

        return app

    except Exception:
        logger.exception('Unhandled startup exception')
        raise
