# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
import logging.config
from pathlib import Path
import socket

from everett.manager import ConfigManager, ConfigOSEnv, ListOf, parse_class
from everett.component import ConfigOptions, RequiredConfigMixin
import falcon
import markus

from antenna.breakpad_resource import BreakpadSubmitterResource
from antenna.health_resource import (
    BrokenResource,
    HeartbeatResource,
    LBHeartbeatResource,
    VersionResource,
)
from antenna.heartbeat import HeartbeatManager
from antenna.sentry import (
    set_sentry_client,
    setup_sentry_logging,
    wsgi_capture_exceptions,
)


logger = logging.getLogger(__name__)


_LOGGING_SETUP = False


def setup_logging(app_config):
    """Initialize Python logging configuration."""
    global _LOGGING_SETUP
    if _LOGGING_SETUP:
        # NOTE(willkg): This makes it so that logging is only set up once per process.
        return

    host_id = app_config("host_id") or socket.gethostname()

    class AddHostID(logging.Filter):
        def filter(self, record):
            record.host_id = host_id
            return True

    dc = {
        "version": 1,
        "disable_existing_loggers": True,
        "filters": {"add_hostid": {"()": AddHostID}},
        "formatters": {
            "socorroapp": {
                "format": "%(asctime)s %(levelname)s - %(name)s - %(message)s"
            },
            "mozlog": {
                "()": "dockerflow.logging.JsonLogFormatter",
                "logger_name": "antenna",
            },
        },
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "socorroapp",
                "filters": ["add_hostid"],
            },
            "mozlog": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "mozlog",
                "filters": ["add_hostid"],
            },
        },
        "loggers": {
            "antenna": {
                "propagate": False,
                "handlers": ["mozlog"],
                "level": app_config("logging_level"),
            }
        },
        "root": {"handlers": ["mozlog"], "level": "WARNING"},
    }

    if app_config("local_dev_env"):
        # In a local development environment, we log to the console in a human-readable
        # fashion and add a markus logger
        dc["loggers"]["antenna"]["handlers"] = ["console"]
        dc["loggers"]["markus"] = {
            "propagate": False,
            "handlers": ["console"],
            "level": "INFO",
        }
        dc["root"]["handlers"] = ["console"]

    logging.config.dictConfig(dc)
    _LOGGING_SETUP = True


def setup_metrics(metrics_classes, config, logger=None):
    """Initialize and configures the metrics system."""
    logger.info("Setting up metrics: %s", metrics_classes)

    markus_configuration = []
    for cls in metrics_classes:
        backend = cls(config)
        log_config(logger, backend)
        markus_configuration.append(backend.to_markus())

    markus.configure(markus_configuration)


def log_config(logger, component):
    """Log configuration for a given component."""
    for namespace, key, val, opt in component.get_runtime_config():
        if namespace:
            namespaced_key = "%s_%s" % ("_".join(namespace), key)
        else:
            namespaced_key = key

        namespaced_key = namespaced_key.upper()

        if "secret" in opt.key.lower() and val:
            msg = "%s=*****" % namespaced_key
        else:
            msg = "%s=%s" % (namespaced_key, val)
        logger.info(msg)


def build_config_manager():
    config = ConfigManager(
        environments=[
            # Pull configuration from environment variables
            ConfigOSEnv()
        ],
        doc=(
            "For configuration help, see "
            "https://antenna.readthedocs.io/en/latest/configuration.html"
        ),
    )

    return config


class AppConfig(RequiredConfigMixin):
    """Application-level config.

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
        "basedir",
        default=str(Path(__file__).parent.parent),
        doc="The root directory for this application to find and store things.",
    )
    required_config.add_option(
        "logging_level",
        default="DEBUG",
        doc="The logging level to use. DEBUG, INFO, WARNING, ERROR or CRITICAL",
    )
    required_config.add_option(
        "local_dev_env",
        default="False",
        parser=bool,
        doc="Whether or not this is a local development environment.",
    )
    required_config.add_option(
        "metrics_class",
        default="antenna.metrics.LoggingMetrics",
        doc=(
            "Comma-separated list of metrics backends to use. Possible options: "
            '"antenna.metrics.LoggingMetrics" and "antenna.metrics.DatadogMetrics"',
        ),
        parser=ListOf(parse_class),
    )
    required_config.add_option(
        "secret_sentry_dsn",
        default="",
        doc=(
            "Sentry DSN to use. See https://docs.sentry.io/quickstart/#configure-the-dsn "
            "for details. If this is not set an unhandled exception logging middleware "
            "will be used instead."
        ),
    )
    required_config.add_option(
        "host_id",
        default="",
        doc=(
            "Identifier for the host that is running Antenna. This identifies this Antenna "
            "instance in the logs and makes it easier to correlate Antenna logs with "
            "other data. For example, the value could be a public hostname, an instance id, "
            "or something like that. If you do not set this, then socket.gethostname() is "
            "used instead."
        ),
    )

    def __init__(self, config):
        self.config_manager = config
        self.config = config.with_options(self)

    def __call__(self, key):
        """Return configuration for given key."""
        return self.config(key)


class AntennaAPI(falcon.API):
    """Falcon API for Antenna."""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._all_resources = {}

        self.hb = HeartbeatManager(config)

    def add_route(self, name, uri_template, resource, *args, **kwargs):
        """Add specified Falcon route.

        :arg str name: friendly name for this route; use alphanumeric characters

        :arg str url_template: Falcon url template for this route

        :arg obj resource: Falcon resource to handl this route

        """
        self._all_resources[name] = resource
        super().add_route(uri_template, resource, *args, **kwargs)

    def get_resource_by_name(self, name):
        """Return registered resource with specified name.

        :arg str name: the name of the resource to get

        :raises KeyError: if there is no resource by that name

        """
        return self._all_resources[name]

    def get_resources(self):
        """Return a list of registered resources."""
        return self._all_resources.values()

    def get_runtime_config(self, namespace=None):
        """Return generator of runtime configuration for all resources."""
        for res in self.get_resources():
            if hasattr(res, "get_runtime_config"):
                yield from res.get_runtime_config(namespace)

    def verify(self):
        """Verify that Antenna is ready to start."""
        self.hb.verify()

    def start_heartbeat(self, is_alive):
        """Start the Antenna heartbeat coroutine."""
        self.hb.start_heartbeat(is_alive)

    def join_heartbeat(self):
        """Join on the Antenna heartbeat coroutine."""
        self.hb.join_heartbeat()


def get_app(config=None):
    """Return AntennaAPI instance."""
    if config is None:
        config = build_config_manager()

    app_config = AppConfig(config)

    # Set a Sentry client if we're so configured
    set_sentry_client(app_config("secret_sentry_dsn"), app_config("basedir"))

    # Set up logging and sentry first, so we have something to log to. Then
    # build and log everything else.
    setup_logging(app_config)

    # Log application configuration
    log_config(logger, app_config)

    # Set up Sentry exception logger if we're so configured
    setup_sentry_logging()

    # Set up metrics
    setup_metrics(app_config("metrics_class"), config, logger)

    # Build the app and heartbeat manager
    app = AntennaAPI(config)

    # Add resources
    app.add_route("breakpad", "/submit", BreakpadSubmitterResource(config))
    app.add_route(
        "version",
        "/__version__",
        VersionResource(config, basedir=app_config("basedir")),
    )
    app.add_route("heartbeat", "/__heartbeat__", HeartbeatResource(config, app))
    app.add_route("lbheartbeat", "/__lbheartbeat__", LBHeartbeatResource(config))
    app.add_route("broken", "/__broken__", BrokenResource(config))

    # Finish logging configuration
    log_config(logger, app)

    # Verify that we're ready to start
    app.verify()

    # Wrap the app in some kind of unhandled exception notification mechanism
    app = wsgi_capture_exceptions(app)

    return app
