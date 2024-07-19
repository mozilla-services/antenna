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

1. Install required software: Docker, make, and git.

2. Clone the repository to your local machine.

   Instructions for cloning are `on the Antenna page in GitHub
   <https://github.com/mozilla-services/antenna>`_.

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

5. Set up local Pub/Sub and GCS services:

   .. code-block:: shell

      $ make setup

   Anytime you want to wipe service state and recreate them, you can re-run
   this make rule.

6. Run with a prod-like fully-functional configuration.

   1. Running:

      .. code-block:: shell

         $ make run

      You should see a lot of output. It'll start out with something like this::

         web_1 | + PORT=8000
         web_1 | + GUNICORN_WORKERS=1
         web_1 | + GUNICORN_WORKER_CLASS=sync
         web_1 | + GUNICORN_MAX_REQUESTS=0
         web_1 | + GUNICORN_MAX_REQUESTS_JITTER=0
         web_1 | + CMD_PREFIX=
         web_1 | + gunicorn --workers=1 --worker-class=sync --max-requests=0 --max-requests-jitter=0 --config=antenna/gunicornhooks.py --log-file=- --error-logfile=- --access-logfile=- --bind 0.0.0.0:8000 antenna.wsgi:application
         web_1 | [2022-09-13 14:21:45 +0000] [8] [INFO] Starting gunicorn 20.1.0
         web_1 | [2022-09-13 14:21:45 +0000] [8] [INFO] Listening at: http://0.0.0.0:8000 (8)
         web_1 | [2022-09-13 14:21:45 +0000] [8] [INFO] Using worker: sync
         web_1 | [2022-09-13 14:21:45 +0000] [9] [INFO] Booting worker with pid: 9
         web_1 | 2022-09-13 14:21:45,461 INFO - antenna - antenna.liblogging - set up logging logging_level=DEBUG debug=True host_id=097fa14aec1e processname=antenna
         web_1 | 2022-09-13 14:21:45,573 DEBUG - antenna - antenna.app - registered GcsCrashStorage.verify_write_to_bucket for verification
         web_1 | 2022-09-13 14:21:45,612 DEBUG - antenna - antenna.app - registered PubSubCrashPublish.verify_topic for verification
         web_1 | 2022-09-13 14:21:45,613 INFO - antenna - antenna.app - BASEDIR=/app
         web_1 | 2022-09-13 14:21:45,613 INFO - antenna - antenna.app - LOGGING_LEVEL=DEBUG
         web_1 | 2022-09-13 14:21:45,613 INFO - antenna - antenna.app - LOCAL_DEV_ENV=True
         web_1 | 2022-09-13 14:21:45,613 INFO - antenna - antenna.app - STATSD_HOST=statsd
         web_1 | 2022-09-13 14:21:45,613 INFO - antenna - antenna.app - STATSD_PORT=8125
         web_1 | 2022-09-13 14:21:45,613 INFO - antenna - antenna.app - STATSD_NAMESPACE=mcboatface
         web_1 | 2022-09-13 14:21:45,613 INFO - antenna - antenna.app - SECRET_SENTRY_DSN=*****
         web_1 | 2022-09-13 14:21:45,613 INFO - antenna - antenna.app - HOST_ID=
         web_1 | 2022-09-13 14:21:45,613 INFO - antenna - antenna.app - CRASHMOVER_CONCURRENT_CRASHMOVERS=8
         web_1 | 2022-09-13 14:21:45,613 INFO - antenna - antenna.app - CRASHMOVER_CRASHSTORAGE_CLASS=antenna.ext.gcs.crashstorage.GcsCrashStorage
         web_1 | 2022-09-13 14:21:45,613 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_CLASS=antenna.ext.pubsub.crashpublish.PubSubCrashPublish
         web_1 | 2022-09-13 14:21:45,614 INFO - antenna - antenna.app - CRASHMOVER_CRASHSTORAGE_BUCKET_NAME=antennabucket
         web_1 | 2022-09-13 14:21:45,614 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_PROJECT_ID=local-dev-socorro
         web_1 | 2022-09-13 14:21:45,614 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_TOPIC_NAME=local_dev_socorro_standard
         web_1 | 2022-09-13 14:21:45,614 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_TIMEOUT=5
         web_1 | 2022-09-13 14:21:45,614 INFO - antenna - antenna.app - BREAKPAD_DUMP_FIELD=upload_file_minidump
         web_1 | 2022-09-13 14:21:45,614 INFO - antenna - antenna.app - BREAKPAD_THROTTLER_RULES=antenna.throttler.MOZILLA_RULES
         web_1 | 2022-09-13 14:21:45,614 INFO - antenna - antenna.app - BREAKPAD_THROTTLER_PRODUCTS=antenna.throttler.MOZILLA_PRODUCTS
         web_1 | 2022-09-13 14:21:45,661 INFO - antenna - markus.backends.datadog - DatadogMetrics configured: statsd:8125 mcboatface
         web_1 | 2022-09-13 14:21:45,668 DEBUG - antenna - antenna.app - Verification starting.
         web_1 | 2022-09-13 14:21:45,669 DEBUG - antenna - antenna.app - Verifying PubSubCrashPublish.verify_topic
         web_1 | 2022-09-13 14:21:45,678 DEBUG - antenna - antenna.app - Verifying GcsCrashStorage.verify_write_to_bucket
         web_1 | 2022-09-13 14:21:45,699 DEBUG - antenna - antenna.app - Verification complete: everything is good!
         web_1 | 2022-09-13 14:21:45,699 INFO - antenna - antenna.app - Antenna is running! http://localhost:8000/
         web_1 | 2022-09-13 14:21:45,700 INFO - antenna - markus - METRICS|2022-09-13 14:21:45|gauge|crashmover.work_queue_size|0|

   2. Verify things are running:

      In another terminal, you can verify the proper containers are running with:

      .. code-block:: shell

         $ docker compose ps

      You should see containers with names ``web``, ``statsd``, ``pubsub`` and ``gcs-emulator``.

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

         web_1 | 2022-09-13 14:23:19,307 INFO - antenna - markus - METRICS|2022-09-13 14:23:19|histogram|breakpad_resource.crash_size|367|#payload:uncompressed
         web_1 | 2022-09-13 14:23:19,308 INFO - antenna - markus - METRICS|2022-09-13 14:23:19|incr|breakpad_resource.incoming_crash|1|
         web_1 | 2022-09-13 14:23:19,327 INFO - antenna - antenna.breakpad_resource - 6214725e-707c-4819-b2b4-93dce0220913: matched by accept_everything; returned ACCEPT
         web_1 | 2022-09-13 14:23:19,328 INFO - antenna - markus - METRICS|2022-09-13 14:23:19|incr|breakpad_resource.throttle_rule|1|#rule:accept_everything
         web_1 | 2022-09-13 14:23:19,328 INFO - antenna - markus - METRICS|2022-09-13 14:23:19|incr|breakpad_resource.throttle|1|#result:accept
         web_1 | 2022-09-13 14:23:19,329 INFO - antenna - markus - METRICS|2022-09-13 14:23:19|timing|breakpad_resource.on_post.time|21.956996999506373|
         web_1 | 2022-09-13 14:23:19,366 INFO - antenna - antenna.crashmover - 6214725e-707c-4819-b2b4-93dce0220913 saved
         web_1 | 2022-09-13 14:23:19,366 INFO - antenna - markus - METRICS|2022-09-13 14:23:19|timing|crashmover.crash_save.time|36.97146700142184|
         web_1 | 2022-09-13 14:23:19,374 INFO - antenna - antenna.crashmover - 6214725e-707c-4819-b2b4-93dce0220913 published
         web_1 | 2022-09-13 14:23:19,374 INFO - antenna - markus - METRICS|2022-09-13 14:23:19|timing|crashmover.crash_publish.time|7.21690399950603|
         web_1 | 2022-09-13 14:23:19,374 INFO - antenna - markus - METRICS|2022-09-13 14:23:19|timing|crashmover.crash_handling.time|67.44074821472168|
         web_1 | 2022-09-13 14:23:19,374 INFO - antenna - markus - METRICS|2022-09-13 14:23:19|incr|crashmover.save_crash.count|1|
         web_1 | 2022-09-13 14:23:22,814 INFO - antenna - markus - METRICS|2022-09-13 14:23:22|gauge|crashmover.work_queue_size|0|

   4. See the data in gcs-emulator:

      The ``gcs-emulator`` container stores data in memory and the data doesn't
      persist between container restarts.

      You can use the ``bin/gcs_cli.py`` to access it:

      .. code-block:: shell

         $ docker compose run --rm web shell python bin/gcs_cli.py list_buckets

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

      app@...$ pytest tests/test_crashstorage.py

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

Pull request summary should indicate the bug the pull request is related to. Use a hyphen between "bug" and the bug ID(s). For example::

    bug-nnnnnnn: removed frog from tree class

For multiple bugs fixed within a single pull request, list the bugs out individually. For example::

   bug-nnnnnnn, bug-nnnnnnn: removed frog from tree class

Pull request descriptions should cover at least some of the following:

1. what is the issue the pull request is addressing?
2. why does this pull request fix the issue?
3. how should a reviewer review the pull request?
4. what did you do to test the changes?
5. any steps-to-reproduce for the reviewer to use to test the changes

After creating a pull request, attach the pull request to the relevant bugs.

We use the `rob-bugson Firefox addon
<https://addons.mozilla.org/en-US/firefox/addon/rob-bugson/>`_. If the pull
request has "bug-nnnnnnn: ..." or "bug-nnnnnnn, bug-nnnnnnn: ..." in the summary, then rob-bugson will see that
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

* `ruff <https://docs.astral.sh/ruff/>`_: code formatting and linting
* `bandit <https://bandit.readthedocs.io/en/latest/>`_: security linting


Git conventions
---------------

First line is a summary of the commit. It should start with the bug number. Use a hyphen between "bug" and the bug ID(s). For example::

   bug-nnnnnnn: summary

For multiple bugs fixed within a single commit, list the bugs out individually. For example::

   bug-nnnnnnn, bug-nnnnnnn: summary

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

   app@...$ pytest tests/test_crashstorage.py

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


Setting up a development container for VS Code
==============================================
The repository contains configuration files to build a
`development container <https://containers.dev/>`_ in the `.devcontainer`
directory. If you have the "Dev Containers" extension installed in VS Code, you
should be prompted whether you want to reopen the folder in a container on
startup. You can also use the "Dev containers: Reopen in container" command
from the command palette. The container has all Python requirements installed.
IntelliSense, type checking, code formatting with Ruff and running the tests
from the test browser are all set up to work without further configuration.

VS Code should automatically start the container, but it may need to be built on
first run:

.. code-block:: shell

   $ make devcontainerbuild

Additionally on mac there is the potential that running git from inside any
container that mounts the current directory to `/app`, such as the development
container, will fail with `fatal: detected dubious ownership in repository at
'/app'`. This is likely related to `mozilla-services/tecken#2872
<https://github.com/mozilla-services/tecken/pull/2872>`_, and can be treated by
running the following command from inside the development container, which will
probably throw exceptions on some git read-only objects that are already owned
by app:app, so that's fine:

.. code-block:: shell

   $ chown -R app:app /app

If you change settings in ``my.env`` you may need to restart the container to
pick up changes:

.. code-block:: shell

   $ make devcontainer
