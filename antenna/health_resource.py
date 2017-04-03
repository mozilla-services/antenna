# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from collections import OrderedDict
import json
import logging

from everett.component import RequiredConfigMixin
import falcon

from antenna import metrics
from antenna.util import get_version_info


logger = logging.getLogger(__name__)
mymetrics = metrics.get_metrics(__name__)


class BrokenResource(RequiredConfigMixin):
    """Implements the ``/__broken__`` endpoint"""
    def __init__(self, config):
        self.config = config

    def on_get(self, req, resp):
        # This is intentional breakage
        raise Exception('intentional exception')


class VersionResource:
    """Implements the ``/__version__`` endpoint"""
    def __init__(self, config, basedir):
        self.config = config
        self.basedir = basedir

    def on_get(self, req, resp):
        version_info = get_version_info(self.basedir)

        resp.content_type = 'application/json; charset=utf-8'
        resp.status = falcon.HTTP_200
        resp.body = version_info


class LBHeartbeatResource:
    """Endpoint to let the load balancing know application health"""
    def __init__(self, config):
        self.config = config

    def on_get(self, req, resp):
        resp.status = falcon.HTTP_200


class HealthState:
    """Object representing health of system"""
    def __init__(self):
        self.errors = []
        self.statsd = {}

    def add_statsd(self, name, key, value):
        """Adds a key -> value gauge"""
        if not isinstance(name, str):
            name = name.__class__.__name__
        self.statsd['%s.%s' % (name, key)] = value

    def add_error(self, name, msg):
        """Adds an error"""
        # Use an OrderedDict here so we can maintain key order when converting
        # to JSON.
        d = OrderedDict([('name', name), ('msg', msg)])
        self.errors.append(d)

    def is_healthy(self):
        return len(self.errors) == 0

    def to_dict(self):
        return OrderedDict([
            ('errors', self.errors),
            ('info', self.statsd)
        ])


class HeartbeatResource:
    """Handles /__heartbeat__"""
    def __init__(self, config, app):
        self.config = config
        self.antenna_app = app

    def on_get(self, req, resp):
        state = HealthState()

        # So we're going to think of Antenna like a big object graph and
        # traverse passing along the HealthState instance. Then, after
        # traversing the object graph, we'll tally everything up and deliver
        # the news.
        for resource in self.antenna_app.get_resources():
            if hasattr(resource, 'check_health'):
                resource.check_health(state)

        # Go through and call gauge for each statsd item.
        for k, v in state.statsd.items():
            mymetrics.gauge(k, v)

        if state.is_healthy():
            resp.status = falcon.HTTP_200
        else:
            resp.status = falcon.HTTP_503
        resp.body = json.dumps(state.to_dict())
