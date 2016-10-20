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
production, see docs_.

1. Clone the repository:

   .. code-block:: shell

      $ git clone https://github.com/mozilla/antenna


2. Install docker 1.10.0+ and docker-compose 1.6.0+ on your machine

3. Build the containers:

   .. code-block:: shell

      $ make build


4. Run with a prod-like fully-functional configuration:

   .. code-block:: shell

      $ make run


   You should see a lot of output starting like this::

      FIXME


   In another terminal, you can verify the proper containers are running:

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


   The ``fakes3`` container will store data in ``./fakes3_root``, so you can
   verify it there.

   When you're done with the process, hit CTRL-C to gracefully kill the docker
   container.

   If you want to run with a different Antenna configuration, put the
   configuration in an env file and then set ``ANTENNA_ENV``. For example:

   .. code-block:: shell

      $ ANTENNA_ENV=my.env make run


   See ``prod.env`` and the docs_ for configuration options.

5. Run tests:

   .. code-block:: shell

      $ make test


   If you need to run specific tests or pass in different arguments, you can run
   bash in the base container and then run ``py.test`` with whatever args you
   want. For example:

   .. code-block:: shell

      $ docker-compose run base bash
      app@...$ py.test

      <pytest output>

      app@...$ py.test tests/unittest/test_crashstorage.py


   We're using py.test_ for a test harness and test discovery.


For more details on running Antenna or hacking on Antenna, see the docs_.

.. _py.test: http://pytest.org/
.. _docs: https://antenna.readthedocs.io/
