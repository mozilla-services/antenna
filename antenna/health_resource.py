# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from collections import OrderedDict
import json

import falcon

from antenna.libdockerflow import get_version_info
from antenna.libmarkus import METRICS


class BrokenResource:
    """Handle ``/__broken__`` endpoint."""

    def on_get(self, req, resp):
        """Implement GET HTTP request."""
        METRICS.incr("collector.health.broken.count")
        # This is intentional breakage
        raise Exception("intentional exception")


class VersionResource:
    """Handle ``/__version__`` endpoint."""

    def __init__(self, basedir):
        self.basedir = basedir

    def on_get(self, req, resp):
        """Implement GET HTTP request."""
        METRICS.incr("collector.health.version.count")
        version_info = get_version_info(self.basedir)

        resp.content_type = "application/json; charset=utf-8"
        resp.status = falcon.HTTP_200
        resp.text = json.dumps(version_info)


class LBHeartbeatResource:
    """Handle ``/__lbheartbeat__`` to let the load balancing know application health."""

    def on_get(self, req, resp):
        """Implement GET HTTP request."""
        METRICS.incr("collector.health.lbheartbeat.count")
        resp.content_type = "application/json; charset=utf-8"
        resp.status = falcon.HTTP_200


class HealthState:
    """Object representing health of system."""

    def __init__(self):
        self.errors = []

    def add_error(self, name, msg):
        """Add an error."""
        # Use an OrderedDict here so we can maintain key order when converting
        # to JSON.
        d = OrderedDict([("name", name), ("msg", msg)])
        self.errors.append(d)

    def is_healthy(self):
        """Return whether this represents a healthy state."""
        return len(self.errors) == 0

    def to_dict(self):
        """Convert state to a dict."""
        return OrderedDict([("errors", self.errors)])


class HeartbeatResource:
    """Handle ``/__heartbeat__`` for app health."""

    def __init__(self, app):
        self.antenna_app = app

    def on_get(self, req, resp):
        """Implement GET HTTP request."""
        METRICS.incr("collector.health.heartbeat.count")
        state = HealthState()

        # So we're going to think of Antenna like a big object graph and
        # traverse passing along the HealthState instance. Then, after
        # traversing the object graph, we'll tally everything up and deliver
        # the news.
        for resource in self.antenna_app.get_resources():
            if hasattr(resource, "check_health"):
                resource.check_health(state)

        if state.is_healthy():
            resp.status = falcon.HTTP_200
        else:
            resp.status = falcon.HTTP_503
        resp.text = json.dumps(state.to_dict())
