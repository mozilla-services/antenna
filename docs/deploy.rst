=============================
Putting Antenna in production
=============================

Antenna is a WSGI application that runs with Gunicorn.

We use nginx in front of that, but you might be able to use other web servers.


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

Will this run in Heroku? I have no idea, but maybe you can make it work for low
volumes?

Will this run on AWS? Yes--that's what we do.

Will this run on [insert favorite environment]? I have no idea, but maybe?


EC2 instance size and scaling
=============================

FIXME(willkg): To be determined.


Rough benchmarks
================

FIXME(willkg): To be determined.
