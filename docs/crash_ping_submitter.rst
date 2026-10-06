====================
Crash ping submitter
====================

.. contents::


Overview
========

The crash ping submitter is a gen 2 Google Cloud Function that receives Firefox
crash pings and submits them to Antenna. Its source lives in this repository,
but it's built and deployed separately from Antenna in the
``socorro/tf/modules/crash_ping_submitter/`` Terraform module in the
webservices-infra repo.

Crash pings contain a subset of crash annotations found in crash reports.
The crash reporter sends crash pings through the Firefox telemetry pipeline,
where the `data platform publishes them to a Pub/Sub topic
<https://mozilla-hub.atlassian.net/browse/DENG-11151>`_. This function
subscribes to that topic.

It is a push subscription, so Pub/Sub POSTs one crash ping per request to the
function's HTTPS trigger. Because the trigger is HTTPS rather than a native
Pub/Sub event trigger, the function is handed the raw push envelope and unwraps
it itself.


Development
===========

The crash ping submitter has its own Docker image, built from
``crash_ping_submitter/Dockerfile``, with its dependencies installed. So it is
tested and linted separately from Antenna::

    just test-crash-ping-submitter
    just lint-crash-ping-submitter

To add or change a dependency, edit ``pyproject.toml`` and then update the
lockfile::

    just uv lock --directory crash_ping_submitter

To build the source zip::

    just build-crash-ping-submitter-zip

To test it locally::

    just run-crash-ping-submitter

Then you can send requests from your host machine::

    curl -X POST localhost:8080 -H 'Content-Type: application/json' --data @crash_ping_submitter/tests/data/pubsub_push_request.json


Deployment
==========

Deploying takes two steps, in two repositories:

1. (antenna) CI uploads a source zip to the cloud function source bucket, and
2. (webservices-infra) ``socorro/tf/modules/crash_ping_submitter/`` is pointed
   at one specific object in that bucket.

In other words, uploading alone will not result in the cloud function being
deployed.

The object is named after the git tree sha of ``crash_ping_submitter/``, so its
name changes only when the function's source does. That means:

* a commit that doesn't touch the function resolves to an object that is
  already in the bucket, so nothing is uploaded.
* reverting the function resolves to the object that version produced the first
  time, so nothing is uploaded.

Each object records the commit and the CI run that produced it in its custom
metadata.


Stage
-----

On every push to the main branch, CI builds the source zip and uploads it to
the stage bucket.


Prod
----

FIXME(CRINGE-368): Update for prod.
