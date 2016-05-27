====================================
Antenna: Prototype Socorro collector
====================================

Prototype Socorro breakpad crash collector that uses gevent allowing it
to all be in one process with non-blocking I/O.

* Free software: Mozilla Public License version 2.0
* Documentation: https://antenna.readthedocs.io/

Status
======

2016-05-27: The things I experimented with here seem viable, but I'm putting
this on the back burner for now.


Quickstart
==========

Install
-------

1. Clone the repo:

   .. code-block:: shell

      $ git clone https://github.com/mozilla/antenna

   .. Note::

      If you plan on doing development, clone your fork of the repo
      instead.

2. Install with pip >= 8:

   .. code-block:: shell

      $ mkvirtualenv antenna
      $ pip install --require-hashes -r requirements-dev.txt
      $ pip install -e .


Running in a dev environment
----------------------------

Use this with gunicorn:

.. code-block:: shell

   $ ANTENNA_INI=settings_dev.ini gunicorn --workers=1 \
        --worker-connections=4 \
        --worker-class=gevent \
        antenna.wsgi:application


For development, it probably makes sense to use one process (``--workers=1``)
that can handle multiple concurrent connections (``--worker-connections=4``).
The number of connections you want to handle simultaneously depends on your
setup and all that.

Make sure you use the ``gevent`` worker class (``--worker-class=gevent``).
Otherwise it's not going to use the gevent WSGI app and then you're not going to
be able to handle multiple network connections concurrently.

Further, you need to specify ``ANTENNA_INI`` variable which points to a ``.ini``
file to use. If you don't want to specify a ``.ini`` file, then you need to
specify the configuration variables as environment variables.


Running tests
-------------

Run this:

.. code-block:: shell

   $ py.test


Tests go in ``tests/``. Data required by tests goes in ``tests/data/``.

We're using py.test_ for a test harness and test discovery. We use WebTest_ for
testing the WSGI application and HTTP requests.

.. _WebTest: http://webtest.pythonpaste.org/en/latest/index.html
.. _py.test: http://pytest.org/

