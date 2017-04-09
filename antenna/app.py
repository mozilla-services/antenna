# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import logging.config
import os
from pathlib import Path
import socket
import sys

from everett.manager import ConfigManager, ConfigEnvFileEnv, ConfigOSEnv, parse_class
from everett.component import ConfigOptions, RequiredConfigMixin
import falcon

from antenna import metrics
from antenna.breakpad_resource import BreakpadSubmitterResource
from antenna.health_resource import (
    BrokenResource,
    HeartbeatResource,
    LBHeartbeatResource,
    VersionResource,
)
from antenna.heartbeat import HeartbeatManager
from antenna.sentry import set_sentry_client, wsgi_capture_exceptions, capture_unhandled_exceptions
from antenna.util import one_line_exception


logger = logging.getLogger(__name__)


def setup_logging(app_config):
    """Initializes Python logging configuration"""
    host_id = app_config('host_id') or socket.gethostname()

    dc = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'development': {
                'format': (
                    '[%(asctime)s] [ANTENNA ' +
                    host_id +
                    ' %(process)d] [%(levelname)s] %(name)s: %(message)s'
                ),
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
                'level': app_config('logging_level'),
            },
        },
    }
    logging.config.dictConfig(dc)


def setup_metrics(metrics_class, config):
    """Initializes the metrics system"""
    logger.info('Setting up metrics: %s', metrics_class)
    metrics.metrics_configure(metrics_class, config)


def log_config(logger, component):
    """Logs configuration for a given component"""
    for namespace, key, val, opt in component.get_runtime_config():
        if namespace:
            namespaced_key = '%s_%s' % ('_'.join(namespace), key)
        else:
            namespaced_key = key

        namespaced_key = namespaced_key.upper()

        if 'secret' in opt.key.lower() and val:
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
    required_config.add_option(
        'host_id',
        default='',
        doc=(
            'Identifier for the host that is running Antenna. This identifies this Antenna '
            'instance in the logs and makes it easier to correlate Antenna logs with '
            'other data. For example, the value could be a public hostname, an instance id, '
            'or something like that. If you do not set this, then socket.gethostname() is '
            'used instead.'
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

        self.hb = HeartbeatManager(config)

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

    def start_heartbeat(self, is_alive, pool):
        self.hb.start_heartbeat(is_alive, pool)


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

        # Set a Sentry client if we're so configured
        set_sentry_client(app_config('secret_sentry_dsn'), app_config('basedir'))

        with capture_unhandled_exceptions():
            setup_logging(app_config)
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

        # Wrap the app in some kind of unhandled exception notification mechanism
        app = wsgi_capture_exceptions(app)

        return app

    except Exception:
        logger.error('Unhandled startup exception: %s', one_line_exception(sys.exc_info()))
        raise
