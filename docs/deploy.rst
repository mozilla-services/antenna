=============================
Putting Antenna in production
=============================

.. contents::


High-level things
=================

Antenna is a Python WSGI application that uses `Gunicorn
<http://gunicorn.org/>`_ as the WSGI server.

We use `nginx <http://nginx.org/>`_ in front of that, but you might be able to
use other web servers.

.. Note::

   Make sure to use HTTPS--don't send your users' crash reports over HTTP.


Gunicorn configuration
======================

For Gunicorn configuration, see ``Dockerfile``. You'll want to set the
following:

``GUNICORN_WORKERS``

    The number of Antenna processes to spin off. We use 2x+1 where x is the
    number of processors on the machine we're using.

    This is the ``workers`` Gunicorn configuration setting.

``GUNICORN_WORKER_CONNECTIONS``

    This is the number of coroutines to spin off to handle incoming HTTP
    connections (crash reports). Gunicorn's default is 1000. That's what
    we use in production.

    Note that the Antenna heartbeat insinuates itself into this coroutine pool,
    so you need 2 at a bare minimum.

    This is the ``worker-connections`` Gunicorn configuration setting.

``GUNICORN_WORKER_CLASS``

    This has to be set to ``gevent``. Antenna does some ``GeventWorker``
    specific things and won't work with anything else.

    This is the ``worker-class`` Gunicorn configuration setting.


Health endpoints
================

Antenna exposes several URL endpoints to help you run it at scale.

``/__lbheartbeat__``

    Always returns an HTTP 200. This tells the load balancer that this Antenna
    instance is handling connections still.

``/__heartbeat__``

    This endpoint returns some more data. Depending on how you have Antenna
    configured, this might do a HEAD on the s3 bucket or other things. It
    returns its findings in the HTTP response body.

``/__version__``

    Returns information related to the git sha being run in the HTTP response
    body.

    For example::

        {
            "commit": "5cc6f5170973c7af2e4bb2097679a82ae5659466",
            "version": "",
            "source": "https://github.com/mozilla-services/antenna",
            "build": "https://circleci.com/gh/mozilla-services/antenna/331"
        }

``/__broken__``

    Intentionally throws an exception that is unhandled. This helps testing
    Sentry or other error monitoring.

    This is a nuissance if abused, so it's worth setting up your webserver to
    require basic auth or something for this endpoint.


Environments
============

Will this run in Heroku? Probably, but you'll need to do some Heroku footwork to
set it up.

Will this run on AWS? Yes--that's what we do.

Will this run on [insert favorite environment]? I have no experience with other
systems, but it's probably the case you can get it to work. If you can't save
crashes to Amazon S3, you can always write your own storage class to save it
somewhere else.


EC2 instance size and scaling
=============================

*Circa 2017*

We're setting up Antenna to run on Amazon EC2 x4.large nodes. Antenna isn't very
CPU intensive, but it is very network intensive (it's essentially an upload
server) and it queues things in memory.

Our cluster is set to autoscale on network in. When network in hits 600,000,000,
then it adds another node to the cluster. Network in is being used as a proxy
for number of incoming crashes.

For Socorro, our median incoming crash is 400k and our typical load is between
1,500 crashes/min.

Antenna on two x4.large nodes can handle 1,500 crashes/min without a problem and
without scaling up.


What happens after Antenna collects a crash?
============================================

Antenna saves the crash to the crash storage system you specify. We save our
crashes to AWS S3.

Then it publishes the crash to the designated crash queue. We queue crashes for
processing with AWS SQS. The processor pulls crash report ids to process from
the AWS SQS queue.


Troubleshooting
===============

Antenna doesn't start up
------------------------

Antenna won't start up if it's configured wrong.

Things to check:

1. If you're using Sentry and it's set up correctly, then Antenna will send
   startup errors to Sentry and you can see it there.

2. Check the logs for startup errors. They'll have the string "Unhandled startup
   exception".

3. Is the configuration correct?


AWS S3 bucket permission issues
-------------------------------

At startup, Antenna will try to Head the AWS S3 bucket and if it fails, will
refuse to start up. It does this so that it doesn't start up, then get a crash
and then fail to submit the crash due to permission issues. At that point, you'd
have lost the crash.

If you're seeing errors like::

    [ERROR] antenna.app: Unhandled startup exception: ... botocore.exceptions.ClientError:
    An error occurred (403) when calling the HeadBucket operation: Forbidden

it means that the credentials that Antenna is using don't have the right
permissions to the AWS S3 bucket.

Things to check:

1. Check the bucket and region that Antenna is configured with. It'll be in the
   logs when Antenna starts up.

2. Check that Antenna has the right AWS credentials.

3. Try using the credentials that Antenna is using to access the bucket.


Logs are getting lost / StatsD data is getting lost
---------------------------------------------------

Depending on how you're collecting logs and StatsD data, it's possible that you
might lose this data if Antenna is under so much load that it's saturating the
network interface.

You might see evidence of this by seeing lines in the logs saying a crash was
saved, but no line indicating it was received. Or vice versa.

You might see evidence of this in StatsD when incoming crashes and saved crashes
off by a large number.

Things to check:

1. What's the network out amount for this node? Is it too low?

2. What happens if you increase the capacity for the node? Or if the node is in
   a cluster, add more nodes to the cluster?


The ``save_queue_size > 0`` and climbing
----------------------------------------

This means Antenna is having trouble keeping up with incoming crashes.

Things to check:

1. Increase or decrease the number in the ``concurrent_crashmovers``
   configuration variable.

   Too many will cause a single crash to take longer to save.

   Too few will reduce the efficiency regarding parallelizing around network I/O
   slowness.

   If you've already tuned this configuration variable, skip this step.

2. Increase the number of nodes in the cluster to better share the load.

3. Increase the node capacity so that it has more network out bandwidth.
