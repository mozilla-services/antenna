# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

import grpc.experimental.gevent as grpc_gevent
import gunicorn.workers.ggevent


logger = logging.getLogger(__name__)


class GeventGrpcWorker(gunicorn.workers.ggevent.GeventWorker):
    """Gevent worker that also patches grpc."""

    def patch(self):
        super().patch()
        grpc_gevent.init_gevent()
