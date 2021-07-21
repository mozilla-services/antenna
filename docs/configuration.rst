=====================
Antenna configuration
=====================

.. contents::


Introduction
============

Antenna uses environment configuration to define its behavior.

The local development environment is configured in the ``my.env`` and
``docker/config/local_dev.env`` env files and that configuration is pulled in
when you run Antenna using ``docker-compose``.

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



Application
===========

First, you need to configure the application-scoped variables.

.. autocomponent:: antenna.app.AntennaAPI
   :hide-classname:
   :case: upper

   These all have sane defaults, so you don't have to configure any of this.


Breakpad crash resource
=======================

.. autocomponent:: antenna.breakpad_resource.BreakpadSubmitterResource
   :show-docstring:
   :case: upper
   :namespace: breakpad


Throttler
=========

.. autocomponent:: antenna.throttler.Throttler
   :show-docstring:
   :case: upper
   :namespace: breakpad_throttler


Crash mover
===========

.. autocomponent:: antenna.crashmover.CrashMover
   :show-docstring:
   :case: upper
   :namespace: crashmover


Crash storage
=============

For crash storage, you have three options one of which is a no-op for debugging.


NoOpCrashStorage
----------------

The ``NoOpCrashStorage`` class is helpful for debugging, but otherwise shouldn't
be used.

.. autocomponent:: antenna.ext.crashstorage_base.NoOpCrashStorage
   :show-docstring:
   :case: upper


Filesystem
----------

The ``FSCrashStorage`` class will save crash data to disk. If you choose this,
you'll want to think about what happens to the crash after Antenna has saved it
and implement that.

.. autocomponent:: antenna.ext.fs.crashstorage.FSCrashStorage
   :show-docstring:
   :case: upper
   :namespace: crashmover_crashstorage

   When set as the CrashMover crashstorage class, configuration
   for this class is in the ``CRASHMOVER_CRASHSTORAGE`` namespace.

   Example::

       CRASHMOVER_CRASHSTORAGE_FS_ROOT=/tmp/whatever


AWS S3
------

The ``S3CrashStorage`` class will save crash data to AWS S3. You might be able
to use this to save to other S3-like systems, but that's not tested or
supported.

.. autocomponent:: antenna.ext.s3.connection.S3Connection
   :show-docstring:
   :case: upper
   :namespace: crashmover_crashstorage

   When set as the CrashMover crashstorage class, configuration
   for this class is in the ``CRASHMOVER_CRASHSTORAGE`` namespace.

   Example::

       CRASHMOVER_CRASHSTORAGE_BUCKET_NAME=mybucket
       CRASHMOVER_CRASHSTORAGE_REGION=us-west-2
       CRASHMOVER_CRASHSTORAGE_ACCESS_KEY=somethingsomething
       CRASHMOVER_CRASHSTORAGE_SECRET_ACCESS_KEY=somethingsomething


.. autocomponent:: antenna.ext.s3.crashstorage.S3CrashStorage
   :show-docstring:
   :case: upper
   :namespace: crashmover_crashstorage

   When set as the CrashMover crashstorage class, configuration
   for this class is in the ``CRASHMOVER_CRASHSTORAGE`` namespace.

   Generally, if the default connection class is fine, you don't need to do any
   configuration here.


Crash publish
=============

For crash publishing, you have two options one of which is a no-op.

NoOpCrashPublish
----------------

The ``NoOpCrashPublish`` class is helpful for debugging and also if you don't
want Antenna to be publishing crash ids somewhere.

.. autocomponent:: antenna.ext.crashpublish_base.NoOpCrashPublish
   :show-docstring:
   :case: upper


AWS SQS
-------

The ``SQSCrashPublish`` class will publish crash ids to an AWS SQS queue.

.. autocomponent:: antenna.ext.sqs.crashpublish.SQSCrashPublish
   :show-docstring:
   :case: upper
   :namespace: crashmover_crashpublish

   When set as the CrashMover crashpublish class, configuration
   for this class is in the ``CRASHMOVER_CRASHPUBLISH`` namespace.
