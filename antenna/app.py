# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
import logging.config
from pathlib import Path

from everett.manager import (
    ConfigManager,
    ConfigOSEnv,
    get_config_for_class,
    Option,
)
import falcon
from falcon.errors import HTTPInternalServerError

from antenna.breakpad_resource import BreakpadSubmitterResource
from antenna.crashmover import CrashMover
from antenna.health_resource import (
    BrokenResource,
    HeartbeatResource,
    LBHeartbeatResource,
    VersionResource,
)
from antenna.heartbeat import HeartbeatManager
from antenna.liblogging import setup_logging, log_config
from antenna.libmarkus import setup_metrics
from antenna.libsentry import setup_sentry


LOGGER = logging.getLogger(__name__)


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


class AntennaAPI(falcon.App):
    """Falcon API for Antenna."""

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
        statsd_namespace = Option(default="", doc="Namespace for statsd metrics.")
        secret_sentry_dsn = Option(
            default="",
            doc=(
                "Sentry DSN to use. See https://docs.sentry.io/quickstart/#configure-the-dsn "
                "for details. If this is not set an unhandled exception logging middleware "
                "will be used instead."
            ),
        )
        host_id = Option(
            default="",
            doc=(
                "Identifier for the host that is running Antenna. This identifies this Antenna "
                "instance in the logs and makes it easier to correlate Antenna logs with "
                "other data. For example, the value could be a public hostname, an instance id, "
                "or something like that. If you do not set this, then socket.gethostname() is "
                "used instead."
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

        self.hb = HeartbeatManager()

    def uncaught_error_handler(self, req, resp, ex, params):
        """Handle uncaught exceptions

        Falcon calls this for exceptions that don't subclass HTTPError. We want
        to log an exception, then kick off Falcon's internal error handling
        code for the HTTP response.

        """
        # We're still in an exception context, so sys.exc_info() still has the details.
        LOGGER.exception("Unhandled exception")
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
            statsd_namespace=self.config("statsd_namespace"),
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
        for key, val in get_config_for_class(self.__class__).items():
            self.config(key)

        self.hb.verify()

    def start_heartbeat(self, is_alive):
        """Start the Antenna heartbeat coroutine."""
        self.hb.start_heartbeat(is_alive)

    def join_heartbeat(self):
        """Join on the Antenna heartbeat coroutine."""
        self.hb.join_heartbeat()


def get_app(config_manager=None):
    """Return AntennaAPI instance."""
    if config_manager is None:
        config_manager = build_config_manager()

    # Set up Sentry
    app_config = config_manager.with_options(AntennaAPI)

    # Set up logging and sentry first, so we have something to log to. Then
    # build and log everything else.
    setup_logging(
        logging_level=app_config("logging_level"),
        debug=app_config("local_dev_env"),
        host_id=app_config("host_id"),
        processname="antenna",
    )
    setup_sentry(
        basedir=app_config("basedir"),
        host_id=app_config("host_id"),
        sentry_dsn=app_config("secret_sentry_dsn"),
    )

    # Build the app and heartbeat manager
    app = AntennaAPI(config_manager)
    app.setup()
    app.verify()

    if app_config("local_dev_env"):
        LOGGER.info("Antenna is running! http://localhost:8000/")

    return app
