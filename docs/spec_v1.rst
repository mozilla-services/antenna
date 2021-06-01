=================================
Antenna Project specification: v1
=================================

.. contents::

:Author:      Will Kahn-Greene
:Last edited: August 28th, 2017


History
=======

https://github.com/mozilla-services/antenna/commits/main/docs/spec_v1.rst


Background
==========

`Socorro <https://github.com/mozilla-services/socorro>`_ is the crash ingestion pipeline
for Mozilla's products including Firefox, Firefox for Android, and others.

When Firefox crashes, the Breakpad crash reporter collects data, generates the
crash payload, and sends it to Socorro via an HTTP POST.

The Socorro collector handles the incoming HTTP POST, extracts the crash from
the HTTP request payload, saves all the parts to AWS S3, and then tells the
processor to process the crash.

There are several problems with the current state of things:

1. Our current and future infrastructures don't work well with the "multiple
   separate components in the same repository" structure we currently have. When
   we do a deployment, we have to deploy and restart everything even if the
   component didn't change.

2. The different components have radically different uptime requirements.

3. The different components have radically different risk profiles and
   permissions requirements.


For these reasons, we want to extract the Socorro collector into a separate
project in a separate repository with separate infrastructure.


Requirements for Antenna
========================

Requirements for v1 of antenna:

1. Handle incoming HTTP POST requests on ``/submit``

   * Handle gzip compressed HTTP POST request bodies--helpful for mobile.
   * Parse ``multipart/form-data`` into a raw crash.

   Antenna should parse HTTP payloads the same way that Socorro collector
   currently does.

   HTTP payloads are large. As of April 29th, 2017:

   * average: 500kb
   * 95%: 1.5mb
   * max: 3mb

2. Throttle the crash

   * Examine the crash and apply throttling rules to it.
   * "Accepted" crashes are saved and processed.
   * "Deferred" crashes are saved, but not processed.
   * Rejected crashes get dropped.

   Throttling system and rules should match what Socorro collector currently
   does.

   .. Note::

      At some point, we could/should move this to the processor, but we can't
      easily do that without also changing the processor at the same time. To
      reduce the scope of this project, we're going to keep throttling in
      Antenna and then rewrite the processor and then maybe move throttling.

3. Generate a crash id and return it to the breakpad client.

   * Generate a crash id using the same scheme we're currently using.
   * Return the crash id to the client so that it can generate urls
     in about:crashes.
   * Content-type for response should be ``text/plain``.
   * Example success response body::

         CrashID=bp-28a40956-d19e-48ff-a2ee-19a932160525

   * Example failure response body::

         Discarded=1

4. Add collector-generated bits to the crash report.

   * Add ``uuid``, ``dump_names``, ``timestamp``, ``submit_timestamp``,
     ``legacy_processing`` and ``percentage`` fields to raw crash.

5. Return crash id to client

   * This ends the HTTP session, so we want to get to this point as soon as
     possible.

6. Upload crash report files to S3

   * Use the same S3 "directory" scheme we're currently using.
   * Keep trying to save until all files are successfully saved.
   * Saving the raw crash file to S3 will trigger an AWS Lambda function to
     notify the processor of the crash to process.

7. Support Ops Dockerflow status endpoints

   * ``/__version__``
   * ``/__heartbeat__``
   * ``/__lbheartbeat__``

8. Support Ops logging requirements

   * Use the new logging infrastructure.

9. Support Ops statsd for metrics

   * Use Datadog.


Crash reports and the current collector
=======================================

Crash reports come in via ``/submit`` as an HTTP POST.

They have a ``multipart/form-data`` content-type.

The payload (HTTP POST request body) may or may not be compressed. If it's
compressed, then we need to uncompress it.

The payload has a bunch of key/val pairs and also one or more binary parts.

Binary parts have filenames related to the dump files on the client's machine and
``application/octet-stream`` content-type.

The uuid and dump names are user-provided data and affect things like filenames
and s3 pseudo-filenames. They should get sanitized.

Possible binary part names:

* ``memory_report``
* ``upload_file_minidump``
* ``upload_file_minidump_browser``
* ``upload_file_minidump_content``
* ``upload_file_minidump_flash1``
* ``upload_file_minidump_flash2``

Some of these come from ``.dmp`` files on the client computer.

Thus an HTTP POST something like this (long lines are wrapped for easier
viewing)::

    Content-Type: multipart/form-data; boundary=------------------------c4ae5238
    f12b6c82

    --------------------------c4ae5238f12b6c82
    Content-Disposition: form-data; name="Add-ons"

    ubufox%40ubuntu.com:3.2,%7B972ce4c6-7e08-4474-a285-3208198ce6fd%7D:48.0,loop
    %40mozilla.org:1.4.3,e10srollout%40mozilla.org:1.0,firefox%40getpocket.com:1
    .0.4,langpack-en-GB%40firefox.mozilla.org:48.0,langpack-en-ZA%40firefox.mozi
    lla.org:48.0
    --------------------------c4ae5238f12b6c82
    Content-Disposition: form-data; name="AddonsShouldHaveBlockedE10s"

    1
    --------------------------c4ae5238f12b6c82
    Content-Disposition: form-data; name="BuildID"

    20160728203720
    --------------------------c4ae5238f12b6c82
    Content-Disposition: form-data; name="upload_file_minidump"; filename="6da34
    99e-f6ae-22d6-1e1fdac8-16464a16.dmp"
    Content-Type: application/octet-stream

    <BINARY CONTENT>
    --------------------------c4ae5238f12b6c82--

    etc.

    --------------------------c4ae5238f12b6c82--


Which gets converted to a ``raw_crash`` like this::

    {
        'dump_checksums': {
            'upload_file_minidump': 'e19d5cd5af0378da05f63f891c7467af'
        },
        'uuid': '00007bd0-2d1c-4865-af09-80bc02160513',
        'submitted_timestamp': '2016-05-13T00:00:00+00:00',
        'timestamp': 1315267200.0',
        'type_tag': 'bp',
        'Add-ons': '...',
        'AddonsShouldHaveBlockedE10s': '1',
        'BuildID': '20160728203720',
        ...
    }


Which ends up in S3 like this::

    v2/raw_crash/000/20160513/00007bd0-2d1c-4865-af09-80bc02160513

        Raw crash in serialized in JSON.

    v1/dump_names/00007bd0-2d1c-4865-af09-80bc02160513

        Map of dump_name to file name serialized in JSON.

    v1/dump/00007bd0-2d1c-4865-af09-80bc02160513

        Raw dump.


HTTP POST request body has previously had problems with null bytes and
non-utf-8 characters. They've taken great pains to make sure it contains
correct utf-8 characters. We still need to do a pass on removing null bytes.

HTTP POSTs for crash reports should always have a content length.

Crash report can contain::

    Throttleable=0

If that's there and 0, then it should skip the throttler and be accepted,
saved and processed.

    https://dxr.mozilla.org/mozilla-central/source/toolkit/crashreporter/CrashSubmit.jsm#282


Crash report can contain::

    crash_id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

We siphon crashes from our prod environment to our dev environment. We want
these crash reports to end up with the same crash id. Thus it's possible for an
incoming crash to have a crash id in the data. If it does have a crash id, we
should use that.


Crash ids
=========

The Socorro collector generates crash ids that look like this::

    de1bb258-cbbf-4589-a673-34f800160918
                                 ^^^^^^^
                                 ||____|
                                 |  yymmdd
                                 |
                                 depth


The "depth" is used by ``FSRadixTreeStorage`` to figure out how many octet
directories to use. That's the only place depth is used and Mozilla doesn't use
``FSRadixTreeStorage`` or any of its subclasses after the collector.

Antenna will (ab)use this character to encode the throttle result so that
the lambda function listening to S3 save events knows which crashes to
put in the processing queue just by looking at the crash id. Thus a crash
id in Antenna looks like this::

    de1bb258-cbbf-4589-a673-34f800160918
                                 ^^^^^^^
                                 ||____|
                                 |  yymmdd
                                 |
                                 throttle result


where "throttle result" is either 0 for ACCEPT (save and process) or 1
for DEFER (save).

One side benefit of this is that we can list the contents of a directory
in the bucket and know which crashes were slated for processing and which
ones weren't by looking at the crash id.


Throttling
==========

We were thinking of moving throttling to the processor, but in the interests of
reducing the amount of work on other parts of Socorro that we'd have to land in
lockstep with migrating to Antenna, we're going to keep the throttler in Antenna
for now.

We should take the existing throttler code, clean it up and use that verbatim.

One thing we're going to change is that we're not going to specify throttling
rules in configuration. Instead, we'll specify a Python dotted path to the
variable holding the throttling rules which will be defined as Python code. That
makes it wayyyyyy easier to write, review, verify correctness and maintain over
time.


Logging
=======

We'll use the new logging infrastructure. Antenna will use the Python logging
system and log to stdout and that will get picked up by the node and sent to the
logging infrastructure.


Metrics
=======

Antenna will use the Datadog Python library to generate stats. These will be
collected by the dd-agent on the node and sent to Datadog.


Test plan
=========

flake8
------

Antenna will have a linter set up to lint the code base.

This will be run by developers and also run by CI for every pull request and
merge to main.

This will help catch:

* silly mistakes, typos, and so on
* maintainability issues like code style, things to avoid in Python, and so on


``tests/unittest/``
-------------------

Antenna will have a set of unit tests and integration tests in the repository
alongside the code that will cover critical behavior for functions, methods, and
classes in the application.

These will be written in pytest.

These will be run by developers and also run by CI for every pull request and
merge to main.

This will help catch:

* bugs in the software
* regressions in behavior


``tests/systemtest/``
---------------------

Antenna will have a system test that verifies node configuration and behavior.

This is critical because we don't want to put a dysfunctional or misconfigured
node in service. If we did, that will cause us to lose crashes sent to that node
because it may not be able to save them to S3.

Nothing is mocked in these tests--everything is live.

This can be run by the developer. This will be run on every node during a
deployment before the node is put in service.

This will help catch:

* configuration issues in the server environment
* permission issues for saving data to to S3
* bugs in the software related to running in a server environment


loadtest
--------

We want to run load tests on a single node as well as a scaling cluster of nodes
to determine:

1. Is Antenna roughly comparable to the Socorro collector it is replacing in
   regards to resource usage under load?

2. How does a single node handle increasing load? At what point does the node
   fall down? What is the performance behavior for a node under load in regards
   to CPU, memory usage, disk usage, network up/down, and throughput.

3. How does a cluster of nodes handle increasing load? Does the system spin up
   new nodes effectively? Do the conditions for scaling up and down work well
   for the specific context of the Antenna application?

4. How does Antenna handle representative load? How about 3x load? How about 10x
   load?

5. How does Antenna handle load over a period of time?


This then informs us whether we need to make changes and what kind of changes we
should make.

We'll do two rounds of load testing. The first round is a "lite" round just to
get us rough answers for basic performance questions.

https://github.com/willkg/antenna-loadtests/tree/antenna-loadtest-lite

Second round will be run multiple times and will be more comprehensive.

https://github.com/mozilla-services/antenna-loadtests

We'll use this load test system going forward whenever we make substantial
changes that might impact performance.


Research and decisions
======================

nginx like telemetry edge vs. python architecture thoughts
----------------------------------------------------------

The current collector has a web process that:

1. handles incoming HTTP requests
2. converts the multipart/form-data HTTP payload into two JSON documents
   (``raw_crash`` and ``dump_names``) and one binary file for each dump
3. throttles the crash based on configured rules
4. generates a crash id and returns it to the breakpad client
5. saves the crash report data files to local disk

Then there's a crashmover process that runs as a service on the same node and:

1. uploads crash report data files to S3
2. adds a message to RabbitMQ with the crashid telling the processor to process
   that crash
3. sends some data to statsd

My first collector rewrite (June 2016-ish) folded the web and crashmover
processes into a single process using asyncio and an eventloop so that we could
return the crash id to the client as quickly as possible, but continue to do the
additional work of uploading to S3 and notifying RabbitMQ. This also has the
nicety that we don't have to use the disk to queue crash reports up and
theoretically we could run this on Heroku [1]_.

.. [1] Heroku can run docker containers now, so it's probably the case we don't
       have to worry about the "only one process!" thing anymore.

My second collector (August 2016-ish) rewrite merely extracted the collector
bits from the existing Socorro code base. I did this attempt figuring it was the
fastest way to extract the collector. However, it left us with two processes. I
abandoned this one, too.

In August 2016, I traded emails with Mark Reid regarding the Telemetry edge
which serves roughly the same purpose as the Socorro collector. At the time,
they had a heka-based edge but were moving to an nginx-based one called
`nginx_moz_ingest <https://github.com/mozilla-services/nginx_moz_ingest>`_. The
edge sends incoming payloads directly to Kafka.

The edge looked interesting, but there are a few things that Socorro needs
currently that the edge doesn't do:

1. Socorro needs to generate and return a CrashID
2. Socorro needs to convert the multipart/form-data payload into two JSON
   documents (``raw_crash`` and ``dump_names``) and one binary file for each
   dump
3. Socorro has large crash reports and needs to save to S3
4. Socorro currently throttles crashes in the collector
5. Socorro currently uses RabbitMQ to queue crashes up for processing

In September 2016 at the work week, I talked with Rob Helmer about this and he
suggested we build it all in nginx using modules similar to what Telemetry did.
He has a basic collector that generates a uuid and saves the crash report to
disk [2]_. We could use a uuid module and then tweak the outcome of that with
the date.

We could move the throttling to the processor. This is tricky because it means
we're making changes to multiple components at the same time which greatly
increases the scope of the project.

At the work week, we decided we can't just send crash payloads to Kafka because
we get too many of them and they're too large.

We could use an nginx S3 upload module to upload it to S3. We had some concerns
about the various S3 failure scenarios and how to deal with those and how doing
everything as an nginx module makes that more tricky. We could instead have
nginx save it to disk and have a service using inotify notice it on disk and
then upload it to S3.

.. [2] Rob's gist: https://gist.github.com/rhelmer/00dd0f9e4076260078367f763bc9aaf3

We could push converting the payload from multipart/form-data to a series of
separate files to the processor, but that heavily affects the processor, the
webapp, and possibly a bunch of other tools.

We could write a lua module for converting in nginx, but that's more work to do.


Given all that, my current thinking is that we've got the following rough options:

1. This is a doable project using nginx, c, lua, and such and follow what
   Telemetry did with the edge, but there are a lot of differences.

   Doing that will likely give us a collector that's closer to the Telemetry
   collector which is nice.

   There are a decent number of things we'd have to figure out how to do in a
   way that mirrors the current collector or this project becomes a lot bigger
   since it'd also involve making changes to the processor, webapp, and any
   thing that uses the raw crash data.

   The current Socorro team has zero experience building nginx modules or using
   lua. It'd take time to level up on these things. Will's done some similar-ish
   things and we could use what Rob and Telemetry have built. Still, we have no
   existing skills here and I suggest this makes it more likely for it to take
   "a long time" to design, implement, review, test, and get to prod.

2. This is a doable project using Python. Doing that will likely give us a
   collector that has a lifetime of like 2 years, thus it's a stopgap between
   now and whatever the future holds.

   We could use Python 2 which expires in a couple of years.

   We could use Python 3 which reduces the compelling need to rewrite it in
   Python 3 later.

   We can't use Python 3's asyncio because the things we need like boto don't
   support it, yet.

   We could use gevent which lets us do asynchronous I/O and has an event loop.

   This is just like one of the earlier collector rewrites I was working on
   (Antenna). The current Socorro team has experience in this field. Further,
   we've reduced the requirements from the original collector, it'd probably
   take "a short time" to design, implement, review, test and push to prod.

   After rewriting the collector, we plan to extract/rewrite other parts of
   Socorro. After that work is done, it should be a lot easier to make chances
   to components and change how data flows through the system and what shape
   it's in.

   After that, we would be in a much better place to switch to something like
   the Telemetry edge.


Given that, I'm inclined to go the Python route. At some point it may prove to
be an unenthusing decision, but I don't think the risks are high enough that
it'll ever be a **wrong** decision.


WSGI framework thoughts
-----------------------

We wanted to use a framework with the following properties:

1. good usage, well maintained, good docs
2. minimal magic
3. minimal dependencies
4. no db
5. easy to write tests against
6. works well with gunicorn and gevent


I spent a few days looking at CherryPy, Flask, Bottle and Falcon. I wrote
prototypes in all of them that used gunicorn and gevent.

Here's my unscientific hand-wavey summaries:

* CherryPy

  We were using it already, so I figured it was worth looking at. It's nice, but
  there's a lot of it and I decided I liked Falcon better.

* Flask

  It's well used, I'm familiar with it, we use it in other places at Mozilla.
  But it includes Jinja2 and a ton of other dependencies and there's some magic
  (thread-local vars, etc).

* Bottle

  I didn't like Bottle at all. It's in one massive file and just didn't appeal
  to me at all.

* Falcon

  Falcon had all the properties I was looking for. It's nice and was easy to
  implement the things I wanted to in the prototype.


I decided to go with Falcon.

We should write the code in such a way that if we decide to switch to something
else, it's not a complete rewrite.


gevent thoughts
---------------

`Falcon <https://falconframework.org/>`_ lists "works great with async libraries
like gevent" as a feature, so it should be fine.

* https://falcon.readthedocs.io/en/stable/index.html?highlight=gevent#features

While looking into whether boto supported Python 3's asyncio, I read several
comments in their issue tracker from people who use boto with gevent without
problems. Interestingly, the boto2 issue tracker has some open issues around
gevent, but the boto3 issue tracker has none. From that anecdata, I think we're
probably fine with boto.

* https://github.com/gevent/gevent/issues/535#issuecomment-162565389
* https://github.com/boto/boto/issues?utf8=%E2%9C%93&q=is%3Aissue%20is%3Aopen%20gevent
* https://github.com/boto/boto3/issues?utf8=%E2%9C%93&q=is%3Aissue%20is%3Aopen%20gevent

I've heard reports that there are problems with New Relic and gevent, but
nothing recent enough to discount the "it's probably fixed by now"
possibilities. Combing their forums suggests some people have problems, but each
one seems to be fixed or alleviated.

* https://discuss.newrelic.com/search?q=gevent

I feel pretty confident that we'll be fine using gevent. A system test and a
load test might tell us more.

Lonnen brought up this article from the Netflix blog where they had problems
switching to async i/o with Zuul 2 which is Java-based:

https://netflixtechblog.com/zuul-2-the-netflix-journey-to-asynchronous-non-blocking-systems-45947377fb5c

There's a lot of big differences between their project and ours. Still, we
should give some thought to alleviating the complexities of debugging
event-driven code and making sure all the libs we use are gevent-friendly.


boto2 vs. boto3
---------------

According to the boto documentation, boto3 is stable and recommended for daily
use.

* boto2: https://boto.cloudhackers.com/en/latest/
* boto3: https://github.com/boto/boto3

Socorro uses boto2. I think we'll go with boto3 because it's the future.


S3 and bucket names
-------------------

AWS Rules for bucket names:

https://docs.aws.amazon.com/AmazonS3/latest/dev/BucketRestrictions.html

Note that they do suggest using periods in bucket names in the rules.

S3 REST requests:

https://docs.aws.amazon.com/AmazonS3/latest/dev/RESTAPI.html

Note, they talk about two styles:

* "virtual hosted-style request" which is like
  ``http://examplebucket.s3-us-west-2.amazonaws.com/puppy.jpg``
* "path-style request" which is like
  ``http://s3-us-west-2.amazonaws.com/examplebucket/puppy.jpg``

Path-style requires that you use the region-specific endpoint. You'll get an
HTTP 307 if you try to access a bucket that's not in US east if you use
endpoints ``http://s3.amazonaws.com`` or an endpoint for a different region than
where the bucket resides.

In the page on virtual hosted-style requests:

https://docs.aws.amazon.com/AmazonS3/latest/dev/VirtualHosting.html

they say:

    When using virtual hosted–style buckets with SSL, the SSL wild card
    certificate only matches buckets that do not contain periods. To work around
    this, use HTTP or write your own certificate verification logic.

Socorro currently uses ``boto.s3.connect_to_region`` and
``boto.s3.connection.OrdinaryCallingFormat``. Buckets are located in us-west-2.

Boto3 changes the API around. Instead of calling it "calling_format", they call
it "addressing_style".

From that I conclude the following:

1. In order to support the s3 buckets we currently have and use SSL, we need to
   continue using path-style requests and specify the region.
2. With boto3, this means specifying the ``region_name`` when creating the
   session client. I'll have to figure out what the default for
   ``addressing_style`` is and if it's not what we want, how to change it.
3. In the future, we shouldn't use dotted names--it doesn't seem like a big
   deal, but it'll probably make things easier.

I think that covers the open questions we had for the s3 crash store in Antenna.
