# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""This module holds bits to make it easier to test Antenna and related scripts.

This contains ``S3Mock`` which is the mocking system we use for recording AWS
S3 HTTP conversations and writing tests that enforce those conversations.

It's in this module because at some point, it might make sense to extract this
into a separate library.

"""

import io
import os

# boto has a vendored version of requests--we want to mock that one.
from botocore.vendored import requests
from botocore.vendored.requests.adapters import BaseAdapter
from botocore.vendored.requests.models import Response

# Note: DOUBLE-VENDORED!
from botocore.vendored.requests.packages.urllib3.response import HTTPResponse


class ThouShaltNotPass(Exception):
    """Raised when an unhandled HTTP request is run."""

    pass


# Map of status code -> reason
CODE_TO_REASON = {
    200: "OK",
    201: "Created",
    204: "No Content",
    206: "Partial Content",
    304: "Not Modified",
    307: "Temporary Redirect",
    403: "Forbidden",
    404: "Not Found",
}


class Step:
    def __init__(self, method, url, body=None, resp=None):
        # Used to match the request
        self.method = method
        self.url = url
        self.body = body

        # Response
        self.resp = resp

    def match(self, request):
        def check_body(request_body):
            if self.body is None:
                return True
            body = request_body.read()
            request_body.seek(0)
            return self.body == body

        return (
            self.method == request.method
            and self.url == request.url
            and check_body(request.body)
        )

    def build_response(self, request):
        status_code = self.resp["status_code"]
        headers = self.resp["headers"]
        body = self.resp["body"]

        response = Response()
        response.status_code = status_code

        if "content-type" not in headers:
            headers["content-type"] = "text/xml"
        if "content-length" not in headers:
            headers["content-length"] = len(body)

        response.raw = HTTPResponse(
            body=io.BytesIO(body),
            headers=headers,
            status=status_code,
            reason=CODE_TO_REASON[status_code],
            preload_content=False,
            decode_content=False,
        )
        response.reason = response.raw.reason

        # From the request
        response.url = request.url
        response.request = request

        response.connection = self

        return response


class FakeAdapter(BaseAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # The expected conversation specified by the developer
        self.expected_conv = []

        # The actual conversation that happened
        self.conv = []

    def add_step(self, **kwargs):
        self.expected_conv.append(Step(**kwargs))

    def send(self, request, *args, **kwargs):
        if self.expected_conv and self.expected_conv[0].match(request):
            step = self.expected_conv.pop(0)
            resp = step.build_response(request)
            self.conv.append((request, step, resp))
            return resp

        # NOTE(willkg): We use print here because fiddling with the logging
        # framework inside test scaffolding is "tricky".
        print(
            "THWARTED SEND: %s\nargs: %r\nkwargs: %r"
            % (
                (
                    request.method,
                    request.url,
                    request.body.read() if request.body is not None else b"",
                ),
                args,
                kwargs,
            )
        )
        raise ThouShaltNotPass("Preventing unexpected .send() call")

    def close(self):
        raise ThouShaltNotPass("Preventing unexpected .close() call")

    def remaining_conversation(self):
        """Returns the remaining conversation to happen"""
        return self.expected_conv


def serialize_request(request):
    """Takes a request object and "serializes" it into bytes

    This can be printed and is HTTP-request-like.

    :arg request: ``botocore.awsrequest.AWSPreparedRequest``

    :returns: bytes of serialized request

    """
    output = []

    def ln(part):
        if isinstance(part, str):
            part = part.encode("utf-8")
        output.append(part)

    ln("%s %s" % (request.method, request.url))
    for key, val in request.headers.items():
        ln("%s: %s" % (key, val))
    ln("")
    if request.body is not None:
        data = request.body.read()
        request.body.seek(0)
    else:
        data = b""
    ln(data)
    ln("")

    return b"\n".join(output)


def serialize_response(response):
    """Takes a response object and "seralizes" it into bytes

    This can be printed and is HTTP-response-like.

    :arg response; ``requests.model.Response``

    :returns: bytes of serialized response

    """
    output = []

    def ln(part):
        if isinstance(part, str):
            part = part.encode("utf-8")
        output.append(part)

    ln("%s %s" % (response.status_code, response.reason))
    for key, val in response.headers.items():
        ln("%s: %s" % (key, val))
    ln("")
    ln(response.content)
    ln("")

    return b"\n".join(output)


class RecordingAdapterShim:
    """Adapter wrapper for recording requests and responses

    Usage::

        # This is the original adapter
        adapter = get_adapter()

        # Generate the shim, wrap the adapter and set the
        # log filename.
        recording_adapter = RecordingAdapterShim()
        recording_adapter.wrapped_adapter = adapter
        recording_adapter.filename = 's3mock.log'

        # Now you have a wrapped adapter that will record HTTP
        # conversations.
        adapter = recording_adapter

    """

    def send(self, request, *args, **kwargs):
        with open(self.filename, "ab") as fp:
            fp.write(b"===================================\n")
            fp.write(b"REQUEST>>>\n")
            fp.write(serialize_request(request))
            fp.write(b"-----\n")

        response = self.wrapped_adapter.send(request, *args, **kwargs)

        with open(self.filename, "ab") as fp:
            fp.write(b"RESPONSE<<<\n")
            fp.write(serialize_response(response))

        return response

    def __getattr__(self, name):
        return getattr(self.wrapped_adapter, name)


class S3Mock:
    """Provide a configurable mock for Boto3's S3 bits.

    Boto3 uses botocore which uses s3transfer which uses requests to do REST
    API calls.

    ``S3Mock`` mocks requests by creating a fake adapter which allows it to
    intercept all outgoing HTTP requests. This lets us do two things:

    1. assert HTTP conversations happen in a specified way in tests
    2. prevent any unexpected HTTP requests from hitting the network
    3. record HTTP conversations so we can verify things are happening
       correctly and write tests


    **Usage**

    ``S3Mock`` is used as a context manager.

    Basic use::

        with S3Mock() as s3:
            # do things here


    Enforce specific conversation flows with S3 by adding one or more
    conversation steps::

        with S3Mock() as s3:
            # Match on request method and url
            s3.add_step(
                method='PUT',
                url='http://fakes3:4569/fakebucket/some/key',
                resp=s3.fake_response(status_code=200)
            )

            # Match on request method, url and body
            s3.add_step(
                method='PUT',
                url='http://fakes3:4569/fakebucket/some/other/key',
                body=b'["upload_file_minidump"]',
                resp=s3.fake_response(status_code=200)
            )

            # ... do whatever here

            # Assert that the entire expected conversation has occurred
            assert s3.remaining_conversation() == []


    In that, the first HTTP request has to be a ``PUT
    http://fakes3:4569/fakebucket/some/key`` and if it's not, then an exception
    is thrown with helpful information. If that's the first request, then the
    ``resp`` is used to generate a response object which is returned.

    The second request has to have the specified method, url and body. If not,
    then an exception is thrown.

    You can specify a method, url and body to match the request.

    ``S3Mock`` has a ``fake_response`` method that will generate a fake response
    to return when the request matches.

    After all the steps and other things that you want to do are done, then you
    can assert that the entire expected conversation has occurred.

    **Recording**

    One of the difficulties with writing tests that assert HTTP conversations
    happen in a certain way is that if the conversation happens over SSL, then
    it's not readable using network sniffing tools. Thus ``S3Mock`` provides a
    record feature that spits out what's going on to the specified file or
    ``s3mock.log``.

    Usage::

        with S3Mock() as s3:
            s3.record(filename='s3mock.log')

            # Do stuff here

    """

    def __init__(self):
        self.adapter = FakeAdapter()

    def __enter__(self):
        self.start_mock()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop_mock()

    def _get_recording_adapter(self, session, url):
        recording_adapter = RecordingAdapterShim()
        recording_adapter.wrapped_adapter = self._real_get_adapter(
            self=session, url=url
        )
        recording_adapter.filename = self._filename_to_record
        return recording_adapter

    def record(self, filename="s3mock.log"):
        """Starts an HTTP conversation recording session

        :arg str filename: The name of the file to log to.

        """
        if os.path.isfile(filename):
            os.remove(filename)

        # FIXME(willkg): Better to curry this instead of saving it as an
        # instance variable and passing it that way.
        self._filename_to_record = filename

        requests.Session.get_adapter = lambda session, url: self._get_recording_adapter(
            session, url
        )

    def stop_recording(self):
        requests.Session.get_adapter = lambda session, url: self.adapter

    def fake_response(self, status_code, headers=None, body=b""):
        """Generates a fake response for a step in an HTTP conversation

        Example::

            with S3Mock() as s3:
                s3.add_step(
                    method='PUT',
                    url='http://fakes3:4569/...',
                    resp=s3.fake_response(status_code=200)
                )

        """
        if headers is None:
            headers = {}

        return {"status_code": status_code, "headers": headers, "body": body}

    def add_step(self, method, url, body=None, resp=None):
        """Adds a step to the expected HTTP conversation

        Generates a step which will match a request on method, url and body and
        return a specified response.

        To build the response, use ``S3Mock.fake_response``. For example::

            with S3Mock() as s3:
                s3.add_step(
                    method='PUT',
                    url='http://fakes3:4569/...',
                    resp=s3.fake_response(status_code=200)
                )


        :arg str method: method to match on (``GET``, ``POST``, ``PUT`` and so on)
        :arg str url: the url to match
        :arg bytes body: the body to match
        :arg dict resp: the response to return--use ``S3Mock.fake_response`` to
            build this

        """
        self.adapter.add_step(method=method, url=url, body=body, resp=resp)

    def start_mock(self):
        self._real_get_adapter = requests.Session.get_adapter
        requests.Session.get_adapter = lambda session, url: self.adapter

    def stop_mock(self):
        requests.Session.get_adapter = self._real_get_adapter
        delattr(self, "_real_get_adapter")

    def remaining_conversation(self):
        """Returns remaining conversation"""
        return self.adapter.remaining_conversation()
