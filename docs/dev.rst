===========
Development
===========

This chapter covers getting started with Antenna using Docker for a local
development environment.

.. contents::
   :local:


Setup quickstart
================

This is a quickstart that uses Docker so you can see how the pieces work. Docker
is also used for local development of Antenna.

For more comprehensive documentation or instructions on how to set this up in
production, see documentation_.

1. Install required software: Docker, docker-compose (1.10+), make, and git.

   **Linux**:

       Use your package manager.

   **OSX**:

       Install `Docker for Mac <https://docs.docker.com/docker-for-mac/>`_ which
       will install Docker and docker-compose.

       Use `homebrew <https://brew.sh>`_ to install make and git::

         $ brew install make git

   **Other**:

       Install `Docker <https://docs.docker.com/engine/installation/>`_.

       Install `docker-compose <https://docs.docker.com/compose/install/>`_.
       You need something higher than 1.10, but less than 2.0.0.

       Install `make <https://www.gnu.org/software/make/>`_.

       Install `git <https://git-scm.com/>`_.

2. Clone the repository to your local machine.

   Instructions for cloning are `on the Socorro page in GitHub
    <https://github.com/mozilla-services/socorro>`_.

3. (*Optional for Linux users*) Set UID and GID for Docker container user.

   If you're on Linux or you want to set the UID/GID of the app user that
   runs in the Docker containers, run:

   .. code-block:: shell

      $ make my.env

   Then edit the file and set the ``ANTENNA_UID`` and ``ANTENNA_GID``
   variables. These will get used when creating the app user in the base image.

   If you ever want different values, change them in ``my.env`` and re-run
   ``make build``.

4. Download and build Antenna docker containers:

   .. code-block:: shell

      $ make build

   Anytime you want to update the containers, you can run ``make build``.

5. Set up local SQS and S3 services:

   .. code-block:: shell

      $ make setup

   Anytime you want to wipe service state and recreate them, you can run ``make
   setup``.

6. Run with a prod-like fully-functional configuration.

   1. Running:

      .. code-block:: shell

         $ make run

      You should see a lot of output. It'll start out with something like this::

         /usr/bin/docker-compose up web
         antenna_statsd_1 is up-to-date
         antenna_localstack_1 is up-to-date
         Starting antenna_web_1 ... done
         Attaching to antenna_web_1
         web_1    | + PORT=8000
         web_1    | + GUNICORN_WORKERS=1
         web_1    | + GUNICORN_WORKER_CONNECTIONS=4
         web_1    | + GUNICORN_WORKER_CLASS=gevent
         web_1    | + GUNICORN_MAX_REQUESTS=0
         web_1    | + GUNICORN_MAX_REQUESTS_JITTER=0
         web_1    | + CMD_PREFIX=
         web_1    | + gunicorn --workers=1 --worker-connections=4 --worker-class=gevent --max-requests=0 --max-requests-jitter=0 --config=antenna/gunicornhooks.py --log-file - --error-logfile=- --access-logfile=- --bind 0.0.0.0:8000 antenna.wsgi:application
         web_1    | [2021-08-04 19:25:30 +0000] [8] [INFO] Starting gunicorn 20.1.0
         web_1    | [2021-08-04 19:25:30 +0000] [8] [INFO] Listening at: http://0.0.0.0:8000 (8)
         web_1    | [2021-08-04 19:25:30 +0000] [8] [INFO] Using worker: gevent
         web_1    | [2021-08-04 19:25:30 +0000] [9] [INFO] Booting worker with pid: 9
         web_1    | 2021-08-04 19:25:30,645 INFO - antenna - antenna.sentry - Removed sentry client
         web_1    | 2021-08-04 19:25:30,663 INFO - antenna - markus.backends.datadog - DatadogMetrics configured: statsd:8125 mcboatface
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - BASEDIR=/app
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - LOGGING_LEVEL=DEBUG
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - LOCAL_DEV_ENV=True
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - STATSD_HOST=statsd
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - STATSD_PORT=8125
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - STATSD_NAMESPACE=mcboatface
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - SECRET_SENTRY_DSN=
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - HOST_ID=
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - CRASHMOVER_CONCURRENT_CRASHMOVERS=2
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - CRASHMOVER_CRASHSTORAGE_CLASS=antenna.ext.s3.crashstorage.S3CrashStorage
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_CLASS=antenna.ext.sqs.crashpublish.SQSCrashPublish
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - CRASHMOVER_CRASHSTORAGE_CONNECTION_CLASS=antenna.ext.s3.connection.S3Connection
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - CRASHMOVER_CRASHSTORAGE_ACCESS_KEY=foo
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - CRASHMOVER_CRASHSTORAGE_SECRET_ACCESS_KEY=*****
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - CRASHMOVER_CRASHSTORAGE_REGION=us-east-1
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - CRASHMOVER_CRASHSTORAGE_ENDPOINT_URL=http://localstack:4566
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - CRASHMOVER_CRASHSTORAGE_BUCKET_NAME=antennabucket
         web_1    | 2021-08-04 19:25:30,673 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_ACCESS_KEY=foo
         web_1    | 2021-08-04 19:25:30,673 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_SECRET_ACCESS_KEY=*****
         web_1    | 2021-08-04 19:25:30,673 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_REGION=us-east-1
         web_1    | 2021-08-04 19:25:30,673 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_ENDPOINT_URL=http://localstack:4566
         web_1    | 2021-08-04 19:25:30,673 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_QUEUE_NAME=local_dev_socorro_standard
         web_1    | 2021-08-04 19:25:30,673 INFO - antenna - antenna.app - BREAKPAD_DUMP_FIELD=upload_file_minidump
         web_1    | 2021-08-04 19:25:30,673 INFO - antenna - antenna.app - BREAKPAD_THROTTLER_RULES=antenna.throttler.MOZILLA_RULES
         web_1    | 2021-08-04 19:25:30,673 INFO - antenna - antenna.app - BREAKPAD_THROTTLER_PRODUCTS=antenna.throttler.MOZILLA_PRODUCTS
         web_1    | 2021-08-04 19:25:30,673 DEBUG - antenna - antenna.heartbeat - Verification starting.
         web_1    | 2021-08-04 19:25:30,673 DEBUG - antenna - antenna.heartbeat - Verifying S3CrashStorage.verify_write_to_bucket
         web_1    | 2021-08-04 19:25:30,682 DEBUG - antenna - antenna.heartbeat - Verifying SQSCrashPublish.verify_queue
         web_1    | 2021-08-04 19:25:30,692 DEBUG - antenna - antenna.heartbeat - Verification complete: everything is good!
         web_1    | 2021-08-04 19:25:30,692 INFO - antenna - antenna.app - Antenna is running! http://localhost:8000
         web_1    | 2021-08-04 19:25:30,692 INFO - antenna - antenna.heartbeat - Starting heartbeat
         web_1    | 2021-08-04 19:25:30,692 DEBUG - antenna - antenna.heartbeat - thump

   2. Verify things are running:

      In another terminal, you can verify the proper containers are running with:

      .. code-block:: shell

         $ docker-compose ps

      You should see containers with names ``web``, ``statsd`` and ``localstack``.

   3. Send in a crash report:

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

         web_1      | [2016-11-07 15:48:45 +0000] [INFO] antenna.breakpad_resource: a448814e-16dd-45fb-b7dd-b0b522161010 received with existing crash_id
         web_1      | [2016-11-07 15:48:45 +0000] [INFO] antenna.breakpad_resource: a448814e-16dd-45fb-b7dd-b0b522161010: matched by is_firefox_desktop; returned ACCEPT
         web_1      | [2016-11-07 15:48:45 +0000] [INFO] antenna.breakpad_resource: a448814e-16dd-45fb-b7dd-b0b522161010 accepted
         web_1      | [2016-11-07 15:48:45 +0000] [INFO] antenna.breakpad_resource: a448814e-16dd-45fb-b7dd-b0b522161010 saved


   4. See the data in localstack:

      The ``localstack`` container stores data in memory and the data doesn't
      persist between container restarts.

      You can use the ``bin/s3_cli.py`` to access it:

      .. code-block:: shell

         $ docker-compose run --rm web shell python bin/s3_cli.py list_buckets

      If you do this a lot, turn it into a shell script.

   5. Look at runtime metrics with Grafana:

      The ``statsd`` container has `Grafana <https://grafana.com/>`_. You can view
      the statsd data via Grafana in your web browser `<http://localhost:9000>`_.

      To log into Grafana, use username ``admin`` and password ``admin``.

      You'll need to set up a Graphite datasource pointed to
      ``http://localhost:8000``.

      The statsd namespace set in the ``dev.env`` file is "mcboatface".

   6. When you're done--stopping Antenna:

      When you're done with the Antenna process, hit CTRL-C to gracefully kill the
      docker web container.


   If you want to run with a different Antenna configuration in the local
   dev environment, adjust your ``my.env`` file.

   See documentation_ for configuration options.

7. Run tests:

   .. code-block:: shell

      $ make test

   If you need to run specific tests or pass in different arguments, you can run
   bash in the base container and then run ``pytest`` with whatever args you
   want. For example:

   .. code-block:: shell

      $ make shell
      app@...$ pytest

      <pytest output>

      app@...$ pytest tests/unittest/test_crashstorage.py

   We're using pytest_ for a test harness and test discovery.


Bugs / Issues
=============

We use `Bugzilla <https://bugzilla.mozilla.org/>`_ for bug tracking.

`Existing bugs <https://bugzilla.mozilla.org/buglist.cgi?quicksearch=product%3Asocorro%20component%3Aantenna>`_

`Write up a new bug
<https://bugzilla.mozilla.org/enter_bug.cgi?format=__standard__&product=Socorro&component=Antenna>`_.

If you want to do work for which there is no bug, please write up a bug first
so we can work out the problem and how to approach a solution.


Code workflow
=============

Bugs
----

Either write up a bug or find a bug to work on.

Assign the bug to yourself.

Work out any questions about the problem, the approach to fix it, and any
additional details by posting comments in the bug.


Pull requests
-------------

Pull request summary should indicate the bug the pull request is related to.
For example::

    bug nnnnnnn: removed from from tree class

Pull request descriptions should cover at least some of the following:

1. what is the issue the pull request is addressing?
2. why does this pull request fix the issue?
3. how should a reviewer review the pull request?
4. what did you do to test the changes?
5. any steps-to-reproduce for the reviewer to use to test the changes

After creating a pull request, attach the pull request to the relevant bugs.

We use the `rob-bugson Firefox addon
<https://addons.mozilla.org/en-US/firefox/addon/rob-bugson/>`_. If the pull
request has "bug nnnnnnn: ..." in the summary, then rob-bugson will see that
and create a "Attach this PR to bug ..." link.

Then ask someone to review the pull request. If you don't know who to ask, look
at other pull requests to see who's currently reviewing things.


Code review
-----------

Pull requests should be reviewed before merging.

Style nits should be covered by linting as much as possible.

Code reviewers should review the changes in the context of the rest of the
system.


Landing code
------------

Once the code has been reviewed and all tasks in CI pass, the pull request
author should merge the code.

This makes it easier for the author to coordinate landing the changes with
other things that need to happen like landing changes in another repository,
data migrations, configuration changes, and so on.

We use "Rebase and merge" in GitHub.


Conventions
===========

For conventions, see:
`<https://github.com/mozilla-services/antenna/blob/main/.editorconfig>`_


Python code conventions
------------------------

All code files need to start with the MPLv2 header::

    # This Source Code Form is subject to the terms of the Mozilla Public
    # License, v. 2.0. If a copy of the MPL was not distributed with this
    # file, You can obtain one at https://mozilla.org/MPL/2.0/.

To lint the code:

.. code-block:: shell

   $ make lint

If you hit issues, use ``# noqa``.

To reformat the code:

.. code-block:: shell

   $ make lintfix

We're using:

* `black <https://black.readthedocs.io/en/stable/>`_:  code formatting
* `flake8 <https://flake8.pycqa.org/en/latest/>`_: linting
* `bandit <https://bandit.readthedocs.io/en/latest/>`_: security linting


Git conventions
---------------

First line is a summary of the commit. It should start with::

   bug nnnnnnn: summary here

After that, the commit should explain *why* the changes are being made and any
notes that future readers should know for context.


Dependencies
============

Python dependencies for all parts of Antenna are in ``requirements.in`` and
compiled using ``pip-compile`` with hashes and dependencies of dependencies in
the ``requirements.txt`` file.

For example, to add ``foobar`` version 5:

1. add ``foobar==5`` to ``requirements.in``
2. run:

   .. code-block:: shell

      make rebuildreqs

   to apply the updates to ``requirements.txt``

3. rebuild your docker environment:

   .. code-block:: shell

      $ make build

If there are problems, it'll tell you.

In some cases, you might want to update the primary and all the secondary
dependencies. To do this, run:

.. code-block:: shell

   $ make updatereqs


Documentation
=============

Documentation for Antenna is build with `Sphinx
<https://www.sphinx-doc.org/en/stable/>`_ and is available on ReadTheDocs. API is
automatically extracted from docstrings in the code.

To build the docs, run this:

.. code-block:: shell

   $ make docs


Testing
=======

To run the tests, run this:

.. code-block:: shell

   $ make test


Tests go in ``tests/``. Data required by tests goes in ``tests/data/``.

If you need to run specific tests or pass in different arguments, you can run
bash in the base container and then run ``pytest`` with whatever args you want.
For example:

.. code-block:: shell

   $ make shell
   app@...$ pytest

   <pytest output>

   app@...$ pytest tests/unittest/test_crashstorage.py

We're using pytest_ for a test harness and test discovery.

.. _pytest: https://pytest.org/


.. _testing-breakpad-crash-reporting:

Testing crash reporting and collection
======================================

When working on Antenna, it helps to be able to send real live crashes to your
development instance. There are a few options:

1. Use Antenna's tools to send a fake crash:

   .. code-block:: bash

      $ make shell
      app@c392a11dbfec:/app$ python -m testlib.mini_poster --url URL

2. Use Firefox and set the ``MOZ_CRASHREPORTER_URL`` environment variable:

   https://firefox-source-docs.mozilla.org/toolkit/crashreporter/crashreporter/index.html#environment-variables-affecting-crash-reporting

   When you type ``about:crashparent`` in the url bar, it'll immediately crash
   the parent process.

   When you type ``about:crashcontent`` in the url bar, it'll immediately crash
   the content process that's running.

   Go to ``about:crashparent`` or ``about:crashcontent``.

   Alternatively, you can manipulate processes from the command line:

   1. Run:

      .. code-block:: shell

        $ ps -aef | grep firefox

      That will list all the Firefox processes that are running.

   2. Find the process id of the Firefox process you want to kill.

      * main process looks something like ``/usr/bin/firefox``
      * content process looks something like
        ``/usr/bin/firefox -contentproc -childID ...``

   3. The ``kill`` command lets you pass a signal to the process. By default,
      it passes ``SIGTERM`` which will kill the process in a way that
      doesn't launch the crash reporter.

      You want to kill the process in a way that *does* launch the crash
      reporter. I've had success with ``SIGABRT`` and ``SIGFPE``. For example::

         kill -SIGABRT <PID>
         kill -SIGFPE <PID>

      What works for you will depend on the operating system and version of
      Firefox you're using.


Capturing an HTTP POST payload for a crash report
=================================================

The HTTP POST payload for a crash report is sometimes handy to have. You can
capture it this way:

1. Run ``nc -l localhost 8000 > http_post.raw`` in one terminal.

2. Run ``MOZ_CRASHREPORTER_URL=http://localhost:8000/submit firefox`` in a
   second terminal.

3. Crash Firefox using one of the methods in
   :ref:`testing-breakpad-crash-reporting`.

4. The Firefox process will crash and the crash report dialog will pop up.
   Make sure to submit the crash, then click on "Quit Firefox" button.

   That will send the crash to ``nc`` which will pipe it to the file.

5. Wait 30 seconds, then close the crash dialog window.

   You should have a raw HTTP POST in ``http_post.raw``.
