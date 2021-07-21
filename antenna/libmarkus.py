# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Holds Everett-configurable shims for Markus metrics backends."""

import logging

import markus


_IS_MARKUS_SETUP = False

LOGGER = logging.getLogger(__name__)


def setup_metrics(statsd_host, statsd_port, statsd_namespace, debug=False):
    """Initialize and configures the metrics system.

    :arg statsd_host: the statsd host to send metrics to
    :arg statsd_port: the port on the host to send metrics to
    :arg statsd_namespace: the namespace (if any) for these metrics
    :arg debug: whether or not to additionally log metrics to the logger

    """
    global _IS_MARKUS_SETUP
    if _IS_MARKUS_SETUP:
        return

    markus_backends = [
        {
            "class": "markus.backends.datadog.DatadogMetrics",
            "options": {
                "statsd_host": statsd_host,
                "statsd_port": statsd_port,
                "statsd_namespace": statsd_namespace,
            },
        }
    ]
    if debug:
        markus_backends.append(
            {
                "class": "markus.backends.logging.LoggingMetrics",
                "options": {
                    "logger_name": "markus",
                    "leader": "METRICS",
                },
            }
        )
    markus.configure(markus_backends)

    _IS_MARKUS_SETUP = True
