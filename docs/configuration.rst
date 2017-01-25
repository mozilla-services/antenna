=====================
Antenna configuration
=====================

.. contents::


Introduction
============

Configuration Antenna is not too hard. You have some basic choices to make. You
codify the configuration into an env file. Then set ``ANTENNA_ENV`` environment
variable to the path to the env file and you're done.

Here's an example. This uses Datadog installed on the EC2 node for metrics and
also IAM bound to the EC2 node that Antenna is running on so it doesn't need S3
credentials for crashstorage.

::

    # Metrics things
    METRICS_CLASS=antenna.metrics.DogStatsdMetrics
    STATSD_NAMESPACE=mcboatface

    # BreakdpadSubmitterResource settings
    CRASHSTORAGE_CLASS=antenna.ext.s3.crashstorage.S3CrashStorage

    # S3CrashStorage and S3Connection settings
    CRASHSTORAGE_BUCKET_NAME=org-myorg-mybucket



Application
===========

First, you need to configure the application-scoped variables.

.. autoconfig:: antenna.app.AppConfig
   :hide-classname:
   :case: upper

   These all have sane defaults, so you don't have to configure any of this.


Metrics
=======

LoggingMetrics
--------------

.. autoconfig:: antenna.metrics.LoggingMetrics
   :show-docstring:
   :case: upper


DogStatsd metrics
-----------------

.. autoconfig:: antenna.metrics.DogStatsdMetrics
   :show-docstring:
   :case: upper


Breakpad crash resource
=======================

.. autoconfig:: antenna.breakpad_resource.BreakpadSubmitterResource
   :show-docstring:
   :case: upper


Throttler
=========

.. autoconfig:: antenna.throttler.Throttler
   :show-docstring:
   :case: upper


Crash storage
=============

For crash storage, you have three options one of which is a no-op for debugging.


NoOpCrashStorage
----------------

The ``NoOpCrashStorage`` class is helpful for debugging, but otherwise shouldn't
be used.

.. autoconfig:: antenna.ext.crashstorage_base.NoOpCrashStorage
   :show-docstring:
   :case: upper


Filesystem
----------

The ``FSCrashStorage`` class will save crash data to disk. If you choose this,
you'll want to think about what happens to the crash after Antenna has saved it
and implement that.

.. autoconfig:: antenna.ext.fs.crashstorage.FSCrashStorage
   :show-docstring:
   :case: upper
   :namespace: crashstorage

   When set as the BreakpadSubmitterResource crashstorage class, configuration
   for this class is in the ``CRASHSTORAGE`` namespace.

   Example::

       CRASHSTORAGE_FS_ROOT=/tmp/whatever


AWS S3
------

The ``S3CrashStorage`` class will save crash data to AWS S3. You might be able
to use this to save to other S3-like systems, but that's not tested or
supported.

.. autoconfig:: antenna.ext.s3.connection.S3Connection
   :show-docstring:
   :case: upper
   :namespace: crashstorage

   When set as the BreakpadSubmitterResource crashstorage class, configuration
   for this class is in the ``CRASHSTORAGE`` namespace.

   Example::

       CRASHSTORAGE_BUCKET_NAME=mybucket
       CRASHSTORAGE_REGION=us-west-2
       CRASHSTORAGE_ACCESS_KEY=somethingsomething
       CRASHSTORAGE_SECRET_ACCESS_KEY=somethingsomething


.. autoconfig:: antenna.ext.s3.crashstorage.S3CrashStorage
   :show-docstring:
   :case: upper
   :namespace: crashstorage

   When set as the BreakpadSubmitterResource crashstorage class, configuration
   for this class is in the ``CRASHSTORAGE`` namespace.

   Generally, if the default connection class is fine, you don't need to do any
   configuration here.


Putting Antenna in production
=============================

Antenna is a WSGI application. We use it with gunicorn and nginx, but it can
be set up in other ways.

Some things to be aware of when you set up Antenna in production:

1. The following endpoints should require basic auth:

   1. ``/__broken__`` -- This throws an exception. It helps to test Sentry
      configuration. It's best to put it behind auth.
   2. ``/__heartbeat__`` -- This is a more intensive health check, so it's best
      to put it behind auth.

2. The S3 connectivity check requires the credentials that Antenna is using to
   be able to list the contents of the bucket.

3. FIXME -- note about scaling based on RAM usage
