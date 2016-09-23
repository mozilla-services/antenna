=========================
Project specification: v1
=========================

..contents::


Requirements
============

Requirements for v1 of antenna:

1. handle incoming HTTP POST requests on ``/submit``

   * Incoming HTTP POST requests can have compressed or uncompressed payloads,
     but we're going to save them without looking at them at all.

2. generate a crash id

   * Use the same scheme we're currently using.

3. return crash id to client

   * This ends the HTTP session, so we want to get to this point as soon as
     possible.

4. upload crash report payload to S3

   * We'll put the crash id in the pseudo-filename.
   * We'll use SNS to alert something else that will notify the processor of the
     new item to process.

5. support Ops Dockerflow status endpoints


nginx vs. python thoughts
=========================

The current collector has a web process that:

1. handles incoming HTTP requests
2. throttles the crash based on configured rules
3. generates a crash id
4. saves the crash report to disk

Then there's a crashmover process that runs as a service and checks the disk for
new crash reports periodically, uploads them to S3 and adds a message to
RabbitMQ. It also does a bunch of statsd things so we can measure what's going
on.

The Telemetry edge which is roughly the same as the Socorro collector uses an
nginx module to handle incoming HTTP requests and sends the payload to kafka. It
also has a separate process running as a service that watches the disk uploads
to S3.

My first collector rewrite folded the web and crashmover processes into a single
process using asyncio and an eventloop so that we could return the crash id to
the client as quickly as possible, but continue to do the additional work of
uploading to S3 and notifying RabbitMQ. This also has the nicety that we don't
have to use the disk to queue crash reports up and theoretically we could run
this on Heroku [1]_.

.. [1] Heroku can run docker containers now, so it's probably the case we don't
       have to worry about the "only one process!" thing anymore.

My second collector rewrite merely extracted the collector bits from the
existing Socorro code base. I did this attempt figuring it was the fastest way
to extract the collector. However, it left us with two processes.

Rob suggested we build it all in nginx using modules similar to what
Telemetry did. He has a basic collector that generates a uuid and saves the
crash report to disk [2]_. We could use a uuid module and then tweak the outcome
of that with the date. Then use an S3 upload module to upload it to S3. We
talked about this a bit at the work week and there was some concern about the
various S3 failure scenarios and how to deal with those and how doing everything
as an nginx module makes that more tricky. We could instead have nginx save it
to disk and have a service using inotify notice it on disk and then upload it to
S3.

.. [2] Rob's gist: https://gist.github.com/rhelmer/00dd0f9e4076260078367f763bc9aaf3


My current thinking is that we've got the following rough options:

1. This is a doable project using nginx, c, lua and such. Doing that will likely
   give us a collector that's closer to the Telemetry collector. That might be a
   nice thing at some point in the future.

   However, the current Socorro team has zero experience building nginx modules
   or using lua. It'd take time to level up on these things. Will's done some
   similar-ish things and we could use what Rob and Telemetry have built. Still,
   we have no existing skills here and I suggest this makes it more likely for
   it to take "a long time" to design, implement, review, test and push to prod.

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
   because we've reduced the requirements from the original collector, it'd
   probably take "a short time" to design, implement, review, test and push to
   prod.


Given that, I'm inclined to go the Python route. At some point it may prove to
be an unenthusing decision, but I don't think the risks are high enough that
it'll ever be a **wrong** decision.


Crash reports
=============

Crash reports come in via ``/submit`` as an HTTP POST.

They have a ``multipart/form-data`` content-type.

The payload (HTTP POST request body) may or may not be compressed. If it's
compressed, then we need to uncompress it.

The payload has a bunch of key/val pairs and also one or more binary parts.

Binary parts have XXX filename and XXX content-type.

The crash_id and dump names are essentially user-provided data and affect things
like filenames and s3 pseudo-filenames. They should get sanitized.

Possible binary part names:

* ``memory_report``
* ``upload_file_minidump``
* ``upload_file_minidump_browser``
* ``upload_file_minidump_content``
* ``upload_file_minidump_flash1``
* ``upload_file_minidump_flash2``

Some of these come from ``.dmp`` files on the client computer.

Thus an HTTP POST something like this::

    FIXME


Which gets converted to a ``raw_crash`` like this::

    FIXME


Which ends up in S3 like this::

    /v2/raw_crash/000/20160920/60db7156-3553-27e3-38900067-31a261ed

        Raw crash in serialized in JSON.

    /v1/dump_names/60db7156-3553-27e3-38900067-31a261ed

        Map of dump_name to file name serialized in JSON.

    /v1/upload_file_minidump_browser/60db7156-3553-27e3-38900067-31a261ed

        Raw dumps.
