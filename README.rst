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
