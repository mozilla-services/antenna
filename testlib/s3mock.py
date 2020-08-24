# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""This module holds bits to make it easier to test Antenna and related scripts.

This contains ``S3Mock`` which is the mocking system we use for writing tests
that enforce HTTP conversations.

It's in this module because at some point, it might make sense to extract this
into a separate library.

"""

import dataclasses
import io
import unittest

from urllib3.response import HTTPResponse


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


@dataclasses.dataclass
class Request:
    method: str
    url: str
    body: io.BytesIO
    headers: dict
    scheme: str
    host: str
    port: int


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
            # The url can be any one of /path, scheme://host/path, or
            # scheme://host:port/path
            and self.url
            in (
                request.url,
                "%s://%s%s" % (request.scheme, request.host, request.url),
                "%s://%s:%s%s"
                % (request.scheme, request.host, request.port, request.url),
            )
            and check_body(request.body)
        )

    def build_response(self, request):
        status_code = self.resp["status_code"]
        headers = self.resp["headers"]
        body = self.resp["body"]

        response = HTTPResponse(
            body=io.BytesIO(body),
            headers=headers,
            status=status_code,
            request_url=request.url,
            request_method=request.method,
            reason=CODE_TO_REASON[status_code],
            preload_content=False,
            decode_content=False,
        )

        if "content-type" not in headers:
            headers["content-type"] = "text/xml"
        if "content-length" not in headers:
            headers["content-length"] = len(body)

        response.request = request

        return response


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

    :arg response; ``urllib3.response.HTTPResponse``

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


class S3Mock:
    """Provide a configurable mock for Boto3's S3 bits.

    Boto3 uses botocore which uses s3transfer which uses urllib3 to do REST API calls.

    ``S3Mock`` mocks urlopen which allows it to intercept all outgoing HTTP requests.
    This lets us do two things:

    1. assert HTTP conversations happen in a specified way in tests
    2. prevent any unexpected HTTP requests from hitting the network


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


    **Troubleshooting**

    If ``S3Mock`` is thwarting you, you can tell it to ``run_on_error`` and it'll
    execute the urlopen and tell you want the response was. It'll also tell you
    what it expected. This helps debugging assertions on HTTP conversations.

    Usage::

        with S3Mock() as s3:
            s3.run_on_error()
            # ... add steps, etc

    """

    def __init__(self):
        # The expected conversation specified by the developer
        self.expected_conv = []

        # The actual conversation that happened
        self.conv = []

        self._patcher = None

        self._run_on_error = False

    def mocked_urlopen(self, pool, method, url, body=None, headers=None, **kwargs):
        req = Request(method, url, body, headers, pool.scheme, pool.host, pool.port)

        if self.expected_conv and self.expected_conv[0].match(req):
            step = self.expected_conv.pop(0)
            resp = step.build_response(req)
            self.conv.append((req, step, resp))
            return resp

        # NOTE(willkg): We use print here because fiddling with the logging
        # framework inside test scaffolding is "tricky".
        print("THWARTED SEND:\nHTTP Request:\n%s" % serialize_request(req))
        if self.expected_conv:
            step = self.expected_conv[0]
            print("Expected:\n%s %s\n%s" % (step.method, step.url, step.body))
        else:
            print("Expected: nothing")

        if self._patcher and self._run_on_error:
            resp = self._patcher.get_original()[0](
                pool, method=method, url=url, body=body, headers=headers, **kwargs
            )
            print("HTTP Response:\n%s" % serialize_response(resp))

        raise ThouShaltNotPass("Preventing unexpected urlopen call")

    def run_on_error(self):
        """Set S3Mock to run the HTTP request if it hits a conversation error."""
        self._run_on_error = True

    def __enter__(self):
        self.start_mock()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop_mock()

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
        self.expected_conv.append(Step(method=method, url=url, body=body, resp=resp))

    def remaining_conversation(self):
        """Returns the remaining conversation to happen"""
        return self.expected_conv

    def start_mock(self):
        def _mocked_urlopen(pool, *args, **kwargs):
            return self.mocked_urlopen(pool, *args, **kwargs)

        path = "urllib3.connectionpool.HTTPConnectionPool.urlopen"
        self._patcher = unittest.mock.patch(path, _mocked_urlopen)
        self._patcher.start()

    def stop_mock(self):
        self._patcher.stop()
        self._patcher = None
