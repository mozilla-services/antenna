=============================
Antenna: Socorro collector v2
=============================

Socorro breakpad crash collector version 2.

* Free software: Mozilla Public License version 2.0.
* Documentation: https://.readthedocs.io

FIXME: In progress.


Running
=======

Use this with gunicorn::

    gunicorn --workers=1 --worker-connections=4 --worker-class=gevent \
        antenna.wsgi:app


It probably makes sense to use one process (``--workers=1``) that can handle
multiple connections at the same time (``--worker-connections=4``). The number
of connections you want to handle simultaneously depends on your setup and all
that.

Make sure you use the ``gevent`` worker class. Otherwise it's not going to
use the gevent WSI app and then you're not going to be able to handle multiple
network connections concurrently.
