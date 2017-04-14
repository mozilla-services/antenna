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
        self.hb_started = False
        self.is_alive = None
        self.hb_greenlet = None

    def start_heartbeat(self, is_alive):
        """Starts the heartbeat coroutine"""
        if self.hb_started:
            return

        self.hb_started = True
        self.is_alive = is_alive

        logger.info('Starting heartbeat')
        self.hb_greenlet = gevent.spawn(self.heartbeat)

    def _heartbeat_beat_once(self):
        for fun in _registered_hb_funs:
            try:
                with capture_unhandled_exceptions():
                    # logger.debug('hb: running %s', fun.__qualname__)
                    fun()
            except Exception:
                logger.exception('Exception thrown while retrieving health stats')

    def heartbeat(self):
        """Heartbeat function

        Every hearbeat_interval seconds, runs registered functions. This will
        capture unhandled exceptions and report them.

        """
        # Keep beating unless the WSGI worker is shutting down
        while self.is_alive():
            logger.debug('thump')
            self._heartbeat_beat_once()
            gevent.sleep(self.heartbeat_interval)

        logger.info('App stopped, so stopping heartbeat.')

        # We're at worker shutdown, so beat until all registered lifers are ok
        # with us shutting down
        while any([fun() for fun in _registered_lifers]):
            logger.debug('thump (finishing up)')
            self._heartbeat_beat_once()

            # Faster beat so we can shutdown sooner
            gevent.sleep(1)

        logger.info('Everything completed.')

    def join_heartbeat(self):
        """Blocks until heartbeat coroutine is done"""
        if self.hb_greenlet is not None:
            self.hb_greenlet.join()


# All functions registered to run during an Antenna heartbeat
_registered_hb_funs = set()


# All functions that return a please-keep-me-alive status
_registered_lifers = set()


def reset_hb_funs():
    """Resets the list of registered hb functions--used for tests"""
    _registered_hb_funs.clear()
    _registered_lifers.clear()


def register_for_heartbeat(fun):
    """Registers a function as one to run during heartbeats"""
    logger.debug('registered %s for heartbeats', fun.__qualname__)
    _registered_hb_funs.add(fun)
    return fun


def register_for_life(fun):
    """Registers a function that returns True if we need to stay alive"""
    logger.debug('registered %s for life', fun.__qualname__)
    _registered_lifers.add(fun)
    return fun
