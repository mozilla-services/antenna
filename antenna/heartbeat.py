# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""The Antenna app has a set of things that need to run at a specified
interval. We call this interval "the heartbeat". Depending on how you have
Antenna configured, different things could be running every heartbeat.

This file provides infrastructure for creating a HeartbeatManager, registering
functions that should run every heartbeat and running functions in a way that
captures unhandled exceptions but doesn't otherwise disturb the heartbeat.

"""

import logging

from everett.component import ConfigOptions, RequiredConfigMixin
import gevent

from antenna.sentry import capture_unhandled_exceptions


logger = logging.getLogger(__name__)


class HeartbeatManager(RequiredConfigMixin):
    """Heartbeat manager

    This holds heartbeat state and the methods used to start, stop and run the
    heartbeat.

    """

    required_config = ConfigOptions()

    # Interval between heartbeats
    heartbeat_interval = 10

    def __init__(self, config):
        self.config = config.with_options(self)
        self.hb_live = False

    def start_heartbeat(self):
        """Starts the heartbeat coroutine"""
        if not self.hb_live:
            self.hb_live = True
            gevent.spawn_later(self.heartbeat_interval, self.heartbeat)

    def stop_heartbeat(self):
        """Tells the heartbeat to stop running

        Note: This doesn't actually kill the heartbeat greenlet because we
        don't know what it might be doing and that could cause integrity
        problems.

        """
        self.hb_live = False

    def heartbeat(self):
        """Heartbeat function

        Every hearbeat_interval seconds, runs registered functions. This will
        capture unhandled exceptions and report them.

        """
        while self.hb_live:
            logger.debug('thump')
            for fun in _registered_hb_funs:
                try:
                    with capture_unhandled_exceptions():
                        logger.debug('hb: running %s', fun.__qualname__)
                        fun()
                except Exception:
                    logger.exception('Exception thrown while retrieving health stats')

            gevent.sleep(self.heartbeat_interval)


# All functions registered to run during an Antenna heartbeat
_registered_hb_funs = set()


def reset_hb_funs():
    """Resets the list of registered hb functions--used for tests"""
    _registered_hb_funs.clear()


def register_for_heartbeat(fun):
    """Registers a function as one to run during heartbeats"""
    logger.debug('registered %s for heartbeats', fun.__qualname__)
    _registered_hb_funs.add(fun)
    return fun
