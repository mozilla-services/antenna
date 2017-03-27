=============================
Putting Antenna in production
=============================

Antenna is a WSGI application that runs with Gunicorn.

We use nginx in front of that, but you might be able to use other web servers.

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
            "source": "https://github.com/mozilla/antenna",
            "build": "https://circleci.com/gh/mozilla/antenna/331"
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
