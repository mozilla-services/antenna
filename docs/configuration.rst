=============
Configuration
=============

.. contents::
   :local:


Introduction
============

Antenna uses environment configuration to define its behavior.

The local development environment is configured in the ``my.env`` and
``docker/config/local_dev.env`` env files and that configuration is pulled in
when you run Antenna using ``docker compose``.

In a server environment, configuration is pulled in from the process environment.

Here's an example. This uses Datadog installed on the EC2 node for metrics and
also IAM bound to the EC2 node that Antenna is running on so it doesn't need S3
credentials for crashstorage.

::

    # Metrics things
    STATSD_NAMESPACE=mcboatface

    # BreakdpadSubmitterResource settings
    CRASHMOVER_CRASHSTORAGE_CLASS=antenna.ext.s3.crashstorage.S3CrashStorage

    # S3CrashStorage and S3Connection settings
    CRASHMOVER_CRASHSTORAGE_BUCKET_NAME=org-myorg-mybucket


Gunicorn configuration
======================

For Gunicorn configuration, see ``Dockerfile``. You'll want to set the
following:

.. everett:option:: GUNICORN_WORKERS
   :parser: str
   :default: "1"

   The number of Antenna processes to spin off. We use 2x+1 where x is the
   number of processors on the machine we're using.

   This is the ``workers`` Gunicorn configuration setting.

   https://docs.gunicorn.org/en/stable/settings.html#workers

   This is used in
   `bin/run_web.sh <https://github.com/mozilla-services/antenna/blob/main/bin/run_web.sh>`_.


.. everett:option:: GUNICORN_WORKER_CONNECTIONS
   :parser: str
   :default: "4"

   This is the number of coroutines to spin off to handle incoming HTTP
   connections (crash reports). Gunicorn's default is 1000. That's what we use
   in production.

   This is the ``worker-connections`` Gunicorn configuration setting.

   https://docs.gunicorn.org/en/stable/settings.html#worker-connections

   This is used in
   `bin/run_web.sh <https://github.com/mozilla-services/antenna/blob/main/bin/run_web.sh>`_.


.. everett:option:: GUNICORN_WORKER_CLASS
   :parser: str
   :default: "sync"

   This is the ``worker-class`` Gunicorn configuration setting.

   https://docs.gunicorn.org/en/stable/settings.html#worker-class

   This is used in
   `bin/run_web.sh <https://github.com/mozilla-services/antenna/blob/main/bin/run_web.sh>`_.


.. everett:option:: GUNICORN_MAX_REQUESTS
   :parser: str
   :default: "0"

   If set to 0, this does nothing.

   For a value greater than 0, the maximum number of requests for the worker to
   serve before Gunicorn restarts the worker.

   This is the ``ma-requests`` Gunicorn configuration setting.

   https://docs.gunicorn.org/en/stable/settings.html#max-requests

   This is used in
   `bin/run_web.sh <https://github.com/mozilla-services/antenna/blob/main/bin/run_web.sh>`_.


.. everett:option:: GUNICORN_MAX_REQUESTS_JITTER
   :parser: str
   :default: "0"

   Maximum jitter to add to ``GUNICORN_MAX_REQUESTS`` setting.

   This is the ``ma-requests-jitter`` Gunicorn configuration setting.

   https://docs.gunicorn.org/en/stable/settings.html#max-requests-jitter

   This is used in
   `bin/run_web.sh <https://github.com/mozilla-services/antenna/blob/main/bin/run_web.sh>`_.


.. everett:option:: CMD_PREFIX
   :default: ""

   Specifies a command prefix to run the Gunicorn process in.

   This is used in
   `bin/run_web.sh <https://github.com/mozilla-services/antenna/blob/main/bin/run_web.sh>`_.


Application
===========

First, you need to configure the application-scoped variables.

.. autocomponentconfig:: antenna.app.AntennaApp
   :hide-name:
   :case: upper
   :show-table:

   These are defaults appropriate for a server environment, so you may not have
   to configure any of this.


Breakpad crash resource
=======================

.. autocomponentconfig:: antenna.breakpad_resource.BreakpadSubmitterResource
   :show-docstring:
   :case: upper
   :namespace: breakpad
   :show-table:


Throttler
=========

.. autocomponentconfig:: antenna.throttler.Throttler
   :show-docstring:
   :case: upper
   :namespace: breakpad_throttler
   :show-table:


Crash mover
===========

.. autocomponentconfig:: antenna.crashmover.CrashMover
   :show-docstring:
   :case: upper
   :namespace: crashmover
   :show-table:


Crash storage
=============

For crash storage, you have three options one of which is a no-op for debugging.


NoOpCrashStorage
----------------

The ``NoOpCrashStorage`` class is helpful for debugging, but otherwise shouldn't
be used.

.. autocomponentconfig:: antenna.ext.crashstorage_base.NoOpCrashStorage
   :show-docstring:
   :case: upper
   :show-table:


Filesystem
----------

The ``FSCrashStorage`` class will save crash data to disk. If you choose this,
you'll want to think about what happens to the crash after Antenna has saved it
and implement that.

.. autocomponentconfig:: antenna.ext.fs.crashstorage.FSCrashStorage
   :show-docstring:
   :case: upper
   :namespace: crashmover_crashstorage
   :show-table:

   When set as the CrashMover crashstorage class, configuration
   for this class is in the ``CRASHMOVER_CRASHSTORAGE`` namespace.

   Example::

       CRASHMOVER_CRASHSTORAGE_FS_ROOT=/tmp/whatever


AWS S3
------

The ``S3CrashStorage`` class will save crash data to AWS S3. You might be able
to use this to save to other S3-like systems, but that's not tested or
supported.

.. autocomponentconfig:: antenna.ext.s3.connection.S3Connection
   :show-docstring:
   :case: upper
   :namespace: crashmover_crashstorage
   :show-table:

   When set as the CrashMover crashstorage class, configuration
   for this class is in the ``CRASHMOVER_CRASHSTORAGE`` namespace.

   Example::

       CRASHMOVER_CRASHSTORAGE_BUCKET_NAME=mybucket
       CRASHMOVER_CRASHSTORAGE_REGION=us-west-2
       CRASHMOVER_CRASHSTORAGE_ACCESS_KEY=somethingsomething
       CRASHMOVER_CRASHSTORAGE_SECRET_ACCESS_KEY=somethingsomething


.. autocomponentconfig:: antenna.ext.s3.crashstorage.S3CrashStorage
   :show-docstring:
   :case: upper
   :namespace: crashmover_crashstorage

   When set as the CrashMover crashstorage class, configuration
   for this class is in the ``CRASHMOVER_CRASHSTORAGE`` namespace.

   Generally, if the default connection class is fine, you don't need to do any
   configuration here.


Google Cloud Storage
--------------------

The ``GcsCrashStorage`` class will save crash data to Google Cloud Storage.

.. autocomponentconfig:: antenna.ext.gcs.crashstorage.GcsCrashStorage
   :show-docstring:
   :case: upper
   :namespace: crashmover_crashstorage
   :show-table:

   When set as the CrashMover crashstorage class, configuration
   for this class is in the ``CRASHMOVER_CRASHSTORAGE`` namespace.

   Example::

       CRASHMOVER_CRASHSTORAGE_BUCKET_NAME=mybucket


Crash publish
=============

For crash publishing, you have two options one of which is a no-op.

NoOpCrashPublish
----------------

The ``NoOpCrashPublish`` class is helpful for debugging and also if you don't
want Antenna to be publishing crash ids somewhere.

.. autocomponentconfig:: antenna.ext.crashpublish_base.NoOpCrashPublish
   :show-docstring:
   :case: upper


Google Pub/Sub
--------------

The ``PubSubCrashPublish`` class will publish crash ids to a Google Pub/Sub
topic.

.. autocomponentconfig:: antenna.ext.pubsub.crashpublish.PubSubCrashPublish
   :show-docstring:
   :case: upper
   :namespace: crashmover_crashpublish
   :show-table:

   When set as the BreakpadSubmitterResource crashpublish class, configuration
   for this class is in the ``CRASHMOVER_CRASHPUBLISH`` namespace.

   You need to set the project id and topic name.


AWS SQS
-------

The ``SQSCrashPublish`` class will publish crash ids to an AWS SQS queue.

.. autocomponentconfig:: antenna.ext.sqs.crashpublish.SQSCrashPublish
   :show-docstring:
   :case: upper
   :namespace: crashmover_crashpublish
   :show-table:

   When set as the CrashMover crashpublish class, configuration
   for this class is in the ``CRASHMOVER_CRASHPUBLISH`` namespace.
