# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from functools import wraps
import logging
import os
import logging.config
from pathlib import Path

from everett.manager import ConfigManager, ConfigEnvFileEnv, ConfigOSEnv, parse_class
from everett.component import ConfigOptions, RequiredConfigMixin
import falcon
from falcon.http_error import HTTPError

from antenna import metrics
from antenna.breakpad_resource import BreakpadSubmitterResource
from antenna.health_resource import HeartbeatResource, LBHeartbeatResource, VersionResource
from antenna.util import LogConfigMixin


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


def log_unhandled(fun):
    @wraps(fun)
    def _log_unhandled(*args, **kwargs):
        try:
            return fun(*args, **kwargs)
        except Exception:
            logger.exception('UNHANDLED EXCEPTION!')
            raise

    return _log_unhandled


class AppConfig(RequiredConfigMixin, LogConfigMixin):
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

    def unhandled_exception_handler(self, ex, req, resp, params):
        # FIXME(willkg): Falcon 1.1 makes error handling better, so we should rewrite
        # this then.

        if not isinstance(ex, HTTPError):
            # Something unhandled happened. We want to log it so we know about it and
            # then let falcon do it's thing.
            logger.exception('Unhandled exception')
        raise

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

    def log_config(self, logger):
        for res in self.get_resources():
            if hasattr(res, 'log_config'):
                res.log_config(logger)


@log_unhandled
def get_app(config=None):
    """Returns AntennaAPI instance"""
    if config is None:
        config = ConfigManager([
            # Pull configuration from env file specified as ANTENNA_ENV
            ConfigEnvFileEnv([os.environ.get('ANTENNA_ENV')]),
            # Pull configuration from environment variables
            ConfigOSEnv()
        ])

    app_config = AppConfig(config)
    setup_logging(app_config('logging_level'))
    setup_metrics(app_config('metrics_class'), config)

    app_config.log_config(logger)

    app = AntennaAPI(config)
    app.add_error_handler(Exception, handler=app.unhandled_exception_handler)

    app.add_route('homepage', '/', HomePageResource(config))
    app.add_route('breakpad', '/submit', BreakpadSubmitterResource(config))
    app.add_route('version', '/__version__', VersionResource(config, basedir=app_config('basedir')))
    app.add_route('heartbeat', '/__heartbeat__', HeartbeatResource(config, app))
    app.add_route('lbheartbeat', '/__lbheartbeat__', LBHeartbeatResource(config))

    app.log_config(logger)
    return app
