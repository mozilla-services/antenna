==========================================
Antenna: Socorro crash ingestion collector
==========================================

Collector for the `Socorro crash ingestion pipeline
<https://socorro.readthedocs.io/>`_ that supports `breakpad-style crash reports
<https://chromium.googlesource.com/breakpad/breakpad>`_.

Uses Python 3, `Gunicorn <https://gunicorn.org/>`_, `gevent
<https://www.gevent.org/>`_, `Falcon <https://falconframework.org/>`_ and some
other things.

* Free software: Mozilla Public License version 2.0
* Code: https://github.com/mozilla-services/antenna/
* Documentation: https://antenna.readthedocs.io/
* Bugs: `Report a bug <https://bugzilla.mozilla.org/enter_bug.cgi?format=__standard__&product=Socorro&component=Antenna>`_
* Community Participation Guidelines: `Guidelines <https://github.com/mozilla-services/antenna/blob/main/CODE_OF_CONDUCT.md>`_


Quickstart
==========

This is a quickstart that uses Docker so you can see how the pieces work. Docker
is also used for local development of Antenna.

For more comprehensive documentation or instructions on how to set this up in
production, see docs_.

1. Clone the repository:

   .. code-block:: shell

      $ git clone https://github.com/mozilla-services/antenna


2. `Install docker 1.10.0+ <https://docs.docker.com/engine/installation/>`_ and
   `install docker-compose 1.6.0+ <https://docs.docker.com/compose/install/>`_
   on your machine

3. Download and build Antenna docker containers:

   .. code-block:: shell

      $ make build

   Anytime you want to update the containers, you can run ``make build``.

4. Set up local Pub/Sub and S3 services:

   .. code-block:: shell

      $ make setup

   Anytime you want to wipe service state and recreate them, you can run ``make
   setup``.

5. Run with a prod-like fully-functional configuration.

   1. Running:

      .. code-block:: shell

         $ make run


      You should see a lot of output. It'll start out with something like this::

         /usr/bin/docker-compose up web
         antenna_localstack-sqs_1 is up-to-date
         antenna_statsd_1 is up-to-date
         antenna_localstack-s3_1 is up-to-date
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
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - CRASHMOVER_CRASHSTORAGE_ENDPOINT_URL=http://localstack-s3:4572
         web_1    | 2021-08-04 19:25:30,672 INFO - antenna - antenna.app - CRASHMOVER_CRASHSTORAGE_BUCKET_NAME=antennabucket
         web_1    | 2021-08-04 19:25:30,673 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_ACCESS_KEY=foo
         web_1    | 2021-08-04 19:25:30,673 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_SECRET_ACCESS_KEY=*****
         web_1    | 2021-08-04 19:25:30,673 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_REGION=us-east-1
         web_1    | 2021-08-04 19:25:30,673 INFO - antenna - antenna.app - CRASHMOVER_CRASHPUBLISH_ENDPOINT_URL=http://localstack-sqs:4576
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

      You should see containers with names ``web``, ``statsd`` and ``localstack-s3``.

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


   4. See the data in localstack-s3:

      The ``localstack-s3`` container stores data in memory and the data
      doesn't persist between container restarts.

      You can use the aws-cli to access it. For example::

        AWS_ACCESS_KEY_ID=foo AWS_SECRET_ACCESS_KEY=foo \
            aws --endpoint-url=http://localhost:5000 \
                --region=us-east-1 \
                s3 ls s3://antennabucket/

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

   See docs_ for configuration options.

6. Run tests:

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


For more details on running Antenna or hacking on Antenna, see the docs_.

.. _pytest: https://docs.pytest.org/en/stable/
.. _docs: https://antenna.readthedocs.io/
