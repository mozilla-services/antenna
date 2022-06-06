# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Monkey patch stdlib with gevent-friendly bits--need to do this here
# before we import anything else. Gunicorn does this too late.
from gevent import monkey

monkey.patch_all()  # noqa


# We set the timeout here to 60 so as to give Antenna enough time to save off
# any crashes in the queue before the worker goes away and crashes are lost
timeout = 60


def post_worker_init(worker):
    """Gunicorn post_worker_init hook handler.

    This kicks off the heartbeat for the app.

    """

    def _is_alive():
        # Returns the ``.alive`` property of the Gunicorn worker instance
        return worker.alive

    worker.wsgi.app.start_heartbeat(is_alive=_is_alive)


def worker_exit(server, worker):
    """Gunicorn worker_exit hook handler.

    This kicks off after a worker has exited, but before the process is gone.

    We need to make sure that we've saved off all the crashes, so we join
    on those things until they're done.

    """
    if hasattr(worker, "wsgi"):
        worker.wsgi.app.join_heartbeat()
