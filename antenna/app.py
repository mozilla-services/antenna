# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
import logging.config
from pathlib import Path
import socket
import sys

from everett.manager import (
    ConfigManager,
    ConfigOSEnv,
    get_config_for_class,
    Option,
)
import falcon
from falcon.errors import HTTPInternalServerError
from fillmore.libsentry import set_up_sentry
from fillmore.scrubber import Scrubber, Rule, SCRUB_RULES_DEFAULT
import sentry_sdk
from sentry_sdk.hub import Hub
from sentry_sdk.integrations.atexit import AtexitIntegration
from sentry_sdk.integrations.boto3 import Boto3Integration
from sentry_sdk.integrations.dedupe import DedupeIntegration
from sentry_sdk.integrations.excepthook import ExcepthookIntegration
from sentry_sdk.integrations.modules import ModulesIntegration
from sentry_sdk.integrations.stdlib import StdlibIntegration
from sentry_sdk.integrations.threading import ThreadingIntegration
from sentry_sdk.integrations.wsgi import SentryWsgiMiddleware
from sentry_sdk.utils import event_from_exception

from antenna.breakpad_resource import BreakpadSubmitterResource
from antenna.crashmover import CrashMover
from antenna.health_resource import (
    BrokenResource,
    HeartbeatResource,
    LBHeartbeatResource,
    VersionResource,
)
from antenna.libdockerflow import get_release_name
from antenna.liblogging import setup_logging, log_config
from antenna.libmarkus import setup_metrics, METRICS


LOGGER = logging.getLogger(__name__)


# Set up Sentry to scrub user ip addresses, exclude frame-local vars, exclude the
# request body, explicitly include integrations, and not use the LoggingIntegration

SCRUB_RULES_ANTENNA = [
    Rule(
        path="request.headers",
        keys=["X-Forwarded-For", "X-Real-Ip"],
        scrub="scrub",
    ),
]


def count_sentry_scrub_error(msg):
    METRICS.incr("collector.sentry_scrub_error", value=1)


def configure_sentry(app_config):
    scrubber = Scrubber(
        rules=SCRUB_RULES_DEFAULT + SCRUB_RULES_ANTENNA,
        error_handler=count_sentry_scrub_error,
    )
    set_up_sentry(
        sentry_dsn=app_config("secret_sentry_dsn"),
        release=get_release_name(app_config("basedir")),
        host_id=app_config("hostname"),
        # Disable frame-local variables
        with_locals=False,
        # Disable request data from being added to Sentry events
        request_bodies="never",
        # All integrations should be intentionally enabled
        default_integrations=False,
        integrations=[
            AtexitIntegration(),
            Boto3Integration(),
            ExcepthookIntegration(),
            DedupeIntegration(),
            StdlibIntegration(),
            ModulesIntegration(),
            ThreadingIntegration(),
        ],
        # Scrub sensitive data
        before_send=scrubber,
    )


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


class AntennaApp(falcon.App):
    """Falcon app for Antenna."""

    class Config:
        basedir = Option(
            default=str(Path(__file__).parent.parent),
            doc="The root directory for this application to find and store things.",
        )
        logging_level = Option(
            default="INFO",
            doc="The logging level to use. DEBUG, INFO, WARNING, ERROR or CRITICAL",
        )
        local_dev_env = Option(
            default="False",
            parser=bool,
            doc="Whether or not this is a local development environment.",
        )
        statsd_host = Option(default="localhost", doc="Hostname for statsd server.")
        statsd_port = Option(default="8125", doc="Port for statsd server.", parser=int)
        secret_sentry_dsn = Option(
            default="",
            doc=(
                "Sentry DSN to use. See https://docs.sentry.io/quickstart/#configure-the-dsn "
                "for details. If this is not set an unhandled exception logging middleware "
                "will be used instead."
            ),
        )
        hostname = Option(
            default=socket.gethostname(),
            doc=(
                "Identifier for the host that is running Antenna. This identifies this Antenna "
                "instance in the logs and makes it easier to correlate Antenna logs with "
                "other data. For example, the value could be a an instance id, pod id, "
                "or something like that.\n"
                "\n"
                "If you do not set this, then ``socket.gethostname()`` is used instead."
            ),
        )

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.config = config_manager.with_options(self)
        self._all_resources = {}

        # This is the crashmover which takes a crash report, saves it, and publishes
        # it
        self.crashmover = CrashMover(config_manager.with_namespace("crashmover"))

        # This is the breakpad resource that handles incoming crash reports POSTed to
        # /submit
        self.breakpad = BreakpadSubmitterResource(
            config=config_manager.with_namespace("breakpad"), crashmover=self.crashmover
        )

    def uncaught_error_handler(self, req, resp, ex, params):
        """Handle uncaught exceptions

        Falcon calls this for exceptions that don't subclass HTTPError. We want
        to log an exception, then kick off Falcon's internal error handling
        code for the HTTP response.

        """
        # NOTE(willkg): we might be able to get rid of the sentry event capture if the
        # FalconIntegration in sentry-sdk gets fixed
        with sentry_sdk.configure_scope() as scope:
            # The SentryWsgiMiddleware tacks on an unhelpful transaction value which
            # makes things hard to find in the Sentry interface, so we stomp on that
            # with the req.path
            scope.transaction.name = req.path
            hub = Hub.current

            event, hint = event_from_exception(
                ex,
                client_options=hub.client.options,
                mechanism={"type": "antenna", "handled": False},
            )

            event["transaction"] = req.path
            hub.capture_event(event, hint=hint)

        LOGGER.error("Unhandled exception", exc_info=sys.exc_info())
        self._compose_error_response(req, resp, HTTPInternalServerError())

    def get_components(self):
        """Return map of namespace -> component for traversing component tree

        This is only used for logging configuration for components that
        are configurable at runtime using Everett.

        """
        return {
            "crashmover": self.crashmover,
            "breakpad": self.breakpad,
        }

    def setup(self):
        # Set up uncaught error handler
        self.add_error_handler(Exception, self.uncaught_error_handler)

        # Log runtime configuration
        log_config(LOGGER, self.config_manager, self)

        # Set up metrics
        setup_metrics(
            statsd_host=self.config("statsd_host"),
            statsd_port=self.config("statsd_port"),
            hostname=self.config("hostname"),
            debug=self.config("local_dev_env"),
        )

        # Set up Dockerflow and health-related routes
        self.add_route(
            "version",
            "/__version__",
            VersionResource(basedir=self.config("basedir")),
        )
        self.add_route("heartbeat", "/__heartbeat__", HeartbeatResource(app=self))
        self.add_route("lbheartbeat", "/__lbheartbeat__", LBHeartbeatResource())
        self.add_route("broken", "/__broken__", BrokenResource())

        # Set up breakpad submission route
        self.add_route("breakpad", "/submit", self.breakpad)

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

    def verify(self):
        """Verify configuration and that Antenna is ready to start."""
        for key in get_config_for_class(self.__class__).keys():
            self.config(key)

        LOGGER.debug("Verification starting.")
        for fun in _registered_verify:
            LOGGER.debug("Verifying %s", fun.__qualname__)
            # Don't handle any exceptions here--just die and let other
            # machinery handle it
            fun()
        LOGGER.debug("Verification complete: everything is good!")


def get_app(config_manager=None):
    """Return AntennaApp instance."""
    if config_manager is None:
        config_manager = build_config_manager()

    # Set up Sentry
    app_config = config_manager.with_options(AntennaApp)

    # Set up logging and sentry first, so we have something to log to. Then
    # build and log everything else.
    setup_logging(
        logging_level=app_config("logging_level"),
        debug=app_config("local_dev_env"),
        host_id=app_config("hostname"),
        processname="antenna",
    )

    configure_sentry(app_config)

    # Build the app and heartbeat manager
    app = AntennaApp(config_manager)
    app.setup()
    app.verify()

    if app_config("local_dev_env"):
        LOGGER.info("Antenna is running! http://localhost:8000/")

    # Wrap app in Sentry WSGI middleware which builds the request section in the
    # Sentry event
    app = SentryWsgiMiddleware(app)

    return app


# All functions registered to run at verification step
_registered_verify = set()


def reset_verify_funs():
    """Reset the list of registered hb functions--used for tests."""
    _registered_verify.clear()


def register_for_verification(fun):
    """Register a function for verification."""
    LOGGER.debug("registered %s for verification", fun.__qualname__)
    _registered_verify.add(fun)
