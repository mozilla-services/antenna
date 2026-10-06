# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import base64
import gzip
import json
import logging
import pathlib

import main
import pytest
import werkzeug.test
import werkzeug.wrappers

DATA_DIR = pathlib.Path(__file__).parent / "data"

# The Glean client id the fixtures were modified to use.
GLEAN_CLIENT_ID = "11111111-1111-1111-1111-111111111111"


def load_fixture(filename):
    """Load a JSON fixture from the data directory."""
    with open(DATA_DIR / filename) as fp:
        return json.load(fp)


def build_request(body):
    """Build the kind of request object functions_framework passes in.

    A flask.Request is a subclass of werkzeug.wrappers.Request. For
    unit tests, it's easier to create the request object through werkzeug.

    This helper accepts data as bytes and JSON. The bytes format is
    for a negative test, since we expect JSON.
    """
    kwargs = {"data": body} if isinstance(body, bytes) else {"json": body}
    builder = werkzeug.test.EnvironBuilder(method="POST", **kwargs)
    return werkzeug.wrappers.Request(builder.get_environ())


def encode_message_data(crash_ping, compress=True, urlsafe=False):
    """Encode a crash ping the way Pub/Sub encodes message data."""
    raw = json.dumps(crash_ping).encode()
    if compress:
        raw = gzip.compress(raw)
    encode = base64.urlsafe_b64encode if urlsafe else base64.b64encode
    return encode(raw).decode()


def build_push_request(data):
    """Build a Pub/Sub push request carrying the given message data."""
    return build_request({"message": {"data": data}})


def test_handles_a_real_push_request(caplog):
    caplog.set_level(logging.INFO)

    response = main.handle_crash_ping(
        build_request(load_fixture("pubsub_push_request.json"))
    )

    assert response == {"msg": "ok"}
    assert f"glean_client_id={GLEAN_CLIENT_ID}" in caplog.text
    assert "document_id=fc1b0253-617f-4ea4-b5f5-c91a9fe6c0f0" in caplog.text


def test_accepts_url_safe_base64(caplog):
    caplog.set_level(logging.INFO)
    data = encode_message_data(load_fixture("crash_ping.json"), urlsafe=True)
    assert any(char in data for char in "-_"), "not exercising the url-safe alphabet"

    assert main.handle_crash_ping(build_push_request(data)) == {"msg": "ok"}
    assert f"glean_client_id={GLEAN_CLIENT_ID}" in caplog.text


def test_accepts_data_that_is_not_compressed(caplog):
    caplog.set_level(logging.INFO)
    data = encode_message_data(load_fixture("crash_ping.json"), compress=False)

    assert main.handle_crash_ping(build_push_request(data)) == {"msg": "ok"}
    assert f"glean_client_id={GLEAN_CLIENT_ID}" in caplog.text
    assert "was not compressed" in caplog.text


def test_acknowledges_a_ping_with_no_client_id(caplog):
    caplog.set_level(logging.INFO)
    crash_ping = load_fixture("crash_ping.json")
    del crash_ping["client_info"]["client_id"]
    data = encode_message_data(crash_ping)

    assert main.handle_crash_ping(build_push_request(data)) == {"msg": "ok"}
    assert "Crash ping has no client id" in caplog.text


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"this is not json", id="body_is_not_json"),
        pytest.param([], id="body_is_not_an_object"),
        pytest.param({}, id="no_message"),
        pytest.param({"message": "nope"}, id="message_is_not_an_object"),
        pytest.param({"message": {}}, id="no_data"),
        pytest.param({"message": {"data": ""}}, id="empty_data"),
        pytest.param({"message": {"data": "!!! not base64 !!!"}}, id="data_not_base64"),
    ],
)
def test_malformed_envelope(body):
    """Negative tests for errors processing the request body."""
    with pytest.raises(main.MalformedMessage):
        main.handle_crash_ping(build_request(body))


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(gzip.compress(b'{"a": 1}')[:8], id="truncated_gzip"),
        pytest.param(b"\x1f\x8bnot actually gzip", id="corrupt_gzip"),
        pytest.param(b"{not json}", id="data_is_not_json"),
        pytest.param(b"[]", id="crash_ping_is_not_an_object"),
        pytest.param(b"{}", id="no_client_info"),
        pytest.param(b'{"client_info": "nope"}', id="client_info_is_not_an_object"),
    ],
)
def test_malformed_crash_ping(raw):
    """Negative test for errors with the payload inside ``message.data``"""
    data = base64.b64encode(raw).decode()

    with pytest.raises(main.MalformedMessage):
        main.handle_crash_ping(build_push_request(data))
