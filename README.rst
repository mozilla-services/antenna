====================================
Antenna: Prototype Socorro collector
====================================

Prototype Socorro breakpad crash collector that uses gevent allowing it
to all be in one process with non-blocking I/O.

* Free software: Mozilla Public License version 2.0
* Documentation: https://antenna.readthedocs.io/


Quickstart
==========

This is a quickstart that uses Docker so you can see how the pieces work. Docker
is also used for local development of Antenna.

For more comprehensive documentation or instructions on how to set this up in
production, see `the manual on ReadTheDocs <https://antenna.readthedocs.io/>`_.

1. Clone the repository:

   .. code-block:: shell

      $ git clone https://github.com/mozilla/antenna

      - OR -

      $ git clone https://github.com/<YOUR-FORK>/antenna

2. Install docker and docker-compose

3. Build:

   .. code-block:: shell

      $ make build

4. Run with a simple development configuration:

   .. code-block:: shell

      $ make run


   You should see a lot of output starting like this::

      FIXME

   In another terminal, you can verify that the web container is running:

   .. code-block:: shell

      $ docker ps
      FIXME


   You can send a crash report into the system and watch it go through the
   steps:

   .. code-block:: shell

      $ ./bin/send_crash_report.sh
      ...
      <curl http output>
      ...
      CrashID=bp-6c43aa7c-7d34-41cf-85aa-55b0d2160622
      *  Closing connection 0

   You should get a CrashID back from the HTTP POST. You'll also see docker
   logging output something like this::

      FIXME

   When you're done with the process, hit CTRL-C to gracefully kill the docker container.

5. Run tests:

   .. code-block:: shell

      $ make test

   If you need to run specific tests or pass in different arguments, you can
   do:

   .. code-block:: shell

      $ docker-compose run web py.test [ARGS]


.. Note::

   The build and run steps use a very simple dev configuration. You can also use
   the "production configuration" which sets things up similar to the production
   Mozilla Crash Stats system by using the ``build-prod`` and ``run-prod`` make
   rules.










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

