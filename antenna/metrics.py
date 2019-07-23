# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Holds Everett-configurable shims for Markus metrics backends."""

import logging

from everett.component import ConfigOptions, RequiredConfigMixin


logger = logging.getLogger(__name__)


class DogStatsdMetrics(RequiredConfigMixin):
    """Configuration for DatadogMetrics backend."""

    required_config = ConfigOptions()
    required_config.add_option(
        "statsd_host", default="localhost", doc="Hostname for the statsd server"
    )
    required_config.add_option(
        "statsd_port", default="8125", doc="Port for the statsd server", parser=int
    )
    required_config.add_option(
        "statsd_namespace", default="", doc="Namespace for these metrics"
    )

    def __init__(self, config):
        self.config = config.with_options(self)

    def to_markus(self):
        """Convert to Markus configuration."""
        return {
            "class": "markus.backends.datadog.DatadogMetrics",
            "options": {
                "statsd_host": self.config("statsd_host"),
                "statsd_port": self.config("statsd_port"),
                "statsd_namespace": self.config("statsd_namespace"),
            },
        }


class LoggingMetrics(RequiredConfigMixin):
    """Configuration for LoggingMetrics backend."""

    required_config = ConfigOptions()

    def __init__(self, config):
        self.config = config

    def to_markus(self):
        """Convert to Markus configuration."""
        return {"class": "markus.backends.logging.LoggingMetrics"}
