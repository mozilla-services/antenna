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


   We're using py.test_ for a test harness and test discovery. We use WebTest_ for
   testing the WSGI application and HTTP requests.


.. Note::

   The build and run steps use a very simple dev configuration. You can also use
   the "production configuration" which sets things up similar to the production
   Mozilla Crash Stats system by using the ``build-prod`` and ``run-prod`` make
   rules.


.. _WebTest: http://webtest.pythonpaste.org/en/latest/index.html
.. _py.test: http://pytest.org/
