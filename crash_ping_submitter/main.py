# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Cloud function that receives Firefox crash pings and submits them to Antenna.

This is deployed as a gen 2 cloud function with an HTTPS trigger. A Pub/Sub push
subscription on the data platform's crash ping topic POSTs one crash ping per
request to the function.

The source for this function is packaged and uploaded to GCS by CI. See
``bin/build_crash_ping_submitter_zip.sh`` and
``.github/workflows/build-and-push.yml``. The resources it is deployed to live
in webservices-infra/socorro/tf/modules/crash_ping_submitter.

"""

import base64
import gzip
import json
import logging

import flask
import functions_framework

LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    format="[%(levelname)s] %(message)s", level=logging.INFO, force=True
)


class MalformedMessage(Exception):
    """Raised when a message is malformed and can't be processed correctly."""


@functions_framework.errorhandler(MalformedMessage)
def handle_malformed_message(exc):
    """Turn a message we can't decode into a 400.

    Pub/Sub treats anything other than a 2xx as a negative acknowledgment and
    redelivers the message, which is what we want: the subscription's dead
    letter policy gives up after max_delivery_attempts and forwards the
    message to the dead letter topic, where it can be inspected.

    Without a configured dead-letter policy, Pub/Sub will retry these perma-
    failures indefinitely.

    """
    LOGGER.error("malformed message: %s", exc)
    return flask.jsonify({"msg": str(exc)}), 400


def is_gzipped(data):
    """Return whether the data is gzip compressed.

    Every gzip stream starts with the same two bytes, 0x1f 0x8b, so use
    this property to check.
    See https://datatracker.ietf.org/doc/html/rfc1952 Section 2.3.1.

    """
    return data[:2] == b"\x1f\x8b"


def decode_crash_ping(data):
    """Decode the crash ping in the ``data`` field of a Pub/Sub message.

    :arg str data: the base64 encoded, usually gzipped, message data

    :returns: the crash ping as a dict

    :raises MalformedMessage: if the data can't be base64 decoded or
    isn't gzipped.

    """
    try:
        # gcloud encodes bytes fields with url-safe base64, while a
        # Pub/Sub POST message encodes bytes fields with standard base64.
        # Using the altchars option allows us to handle both scenarios.
        raw = base64.b64decode(data, altchars=b"-_")
    except ValueError as exc:
        raise MalformedMessage(f"data is not base64: {exc}") from exc

    # The Glean pipeline compresses payloads, unless it hits a compression
    # error.
    # https://github.com/mozilla/gcp-ingestion/blob/65efa337e606226c01fb2411869c21cb9147bbc1/ingestion-beam/src/main/java/com/mozilla/telemetry/transforms/CompressPayload.java#L64-L71
    #
    # The message.attributes.client_compression in the payload refers
    # to a separate, earlier compression from the client during upload, so
    # we cannot rely on it to check.
    # https://github.com/mozilla/gcp-ingestion/blob/65efa337e606226c01fb2411869c21cb9147bbc1/ingestion-beam/src/main/java/com/mozilla/telemetry/transforms/DecompressPayload.java#L81-L83
    if is_gzipped(raw):
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError) as exc:
            raise MalformedMessage(f"Data is not gzipped: {exc}.") from exc
    else:
        LOGGER.warning("Crash ping data was not compressed.")

    try:
        crash_ping = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MalformedMessage(f"Data is not JSON: {exc}.") from exc

    if not isinstance(crash_ping, dict):
        raise MalformedMessage("Crash ping is not a JSON object.")

    return crash_ping


@functions_framework.http
def handle_crash_ping(request: flask.Request):
    """Handle one crash ping delivered by a Pub/Sub push subscription."""
    envelope = request.get_json(silent=True)
    if not isinstance(envelope, dict):
        raise MalformedMessage("Request body is not a JSON object.")

    message = envelope.get("message")
    if not isinstance(message, dict):
        raise MalformedMessage("Request body has no Pub/Sub message.")

    data = message.get("data")
    if not data:
        raise MalformedMessage("Pub/Sub message has no data.")

    crash_ping = decode_crash_ping(data)

    client_info = crash_ping.get("client_info")
    if not isinstance(client_info, dict):
        raise MalformedMessage("Crash ping has no client_info.")

    attributes = message.get("attributes") or {}
    document_id = attributes.get("document_id")
    glean_client_id = client_info.get("client_id")

    # FIXME(bdanforth): CRINGE-370: Submit the crash ping to Antenna. For now,
    # this only checks that we can get the Glean client id from a crash ping.
    if glean_client_id is None:
        LOGGER.warning("Crash ping has no client id: document_id=%s.", document_id)
    else:
        LOGGER.info(
            "Crash ping has a client id: glean_client_id=%s, document_id=%s.",
            glean_client_id,
            document_id,
        )

    return {"msg": "ok"}
