# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import gc

import gevent
from gevent.pool import Pool


def _start_heartbeat(worker):
    """Runs 2 seconds after post_worker_init

    This starts the heartbeat infrastructure with an appropriate ``is_alive``
    function and the Pool the heartbeat needs to be started in so that it can
    prevent Antenna from shutting down before all the s3 crashes have saved.

    """
    # worker.wsgi is whatever antenna.app.get_app() returned. But that app is
    # wrapped by either Sentry WSGI middleware or a logging WSGI middleware.
    # Both of those classes have a property ``.application`` that is the
    # wrapped WSGI app. If that structure ever changes, we'll need to update
    # this.
    app = worker.wsgi.application

    def _is_alive():
        # Returns the ``.alive`` property of the Gunicorn worker instance
        return worker.alive

    cfg = worker.cfg

    worker_connections = cfg.worker_connections

    # Find a gevent.pool.Pool instance that has size equal to
    # worker_connections value. This is likely the incoming connections Pool.
    #
    # FIXME(willkg): It would be awesome if there were a better way to do this,
    # but every method I found is a gross trade-off. Since the value of
    # worker_connections is 1000, this seems pretty safe.
    for obj in gc.get_objects():
        if isinstance(obj, Pool):
            if obj.size == worker_connections:
                pool = obj
                break
    else:
        print('No Pool instantiated with %s slots.' % worker_connections)
        return

    app.start_heartbeat(is_alive=_is_alive, pool=pool)


def post_worker_init(worker):
    """Gunicorn post_worker_init hook handler

    This spins off a coroutine to run in 2 seconds.

    We can't run it now, since the worker is initialized, but ``.run()`` hasn't
    been called and thus it hasn't created the Pool we need, yet.

    I hand-wavingly think that 2 seconds is long enough that the Pool we want
    has been created, but short enough that it's unlikely the node has been
    flooded such that all 1000 slots in the Pool have been filled already and
    there isn't room for the heartbeat.

    """
    gevent.spawn_later(2, _start_heartbeat, worker)
    print('Done hb spawn')
