# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""This is a Python-3 compatible re-write of a multi-part/form-data encoder heavily
inspired by poster <https://bitbucket.org/chrisatlee/poster>.

The API is similar, but the implementation consists of just the bits that we
wanted in Antenna.

Further, this module can be executed at the command line. Do this for help::

    python -m testlib.mini_poster --help

It can send crashes and dumps and compress them and make you french toast.

"""

import argparse
from email.header import Header
import gzip
import io
import json
import logging
from pathlib import Path
import sys
import uuid

import requests


logger = logging.getLogger(__name__)


def _log_everything():
    # Set up all the debug logging for grossest possible output
    from http.client import HTTPConnection

    HTTPConnection.debuglevel = 1

    logging.getLogger("requests").setLevel(logging.DEBUG)
    logging.getLogger("requests.packages.urllib3").setLevel(logging.DEBUG)


def assemble_crash_payload_dict(raw_crash, dumps, use_json=False):
    """Return a dict form of the payload."""
    crash_data = {}
    if use_json:
        crash_data["extra"] = json.dumps(raw_crash)
    else:
        crash_data.update(raw_crash)

    if dumps:
        for name, contents in dumps.items():
            if isinstance(contents, str):
                contents = contents.encode("utf-8")
            elif not isinstance(contents, bytes):
                contents = str(contents).encode("utf-8")
            crash_data[name] = ("fakecrash.dump", io.BytesIO(contents))

    return crash_data


def compress(multipart):
    """Takes a multi-part/form-data payload and compresses it

    :arg multipart: a bytes object representing a multi-part/form-data

    :returns: bytes compressed

    """
    bio = io.BytesIO()
    g = gzip.GzipFile(fileobj=bio, mode="w")
    g.write(multipart)
    g.close()
    return bio.getbuffer()


def multipart_encode(raw_crash, boundary=None):
    """Takes a raw_crash as a Python dict and converts to a multipart/form-data

    Here's an example ``raw_crash``::

        {
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', io.BytesIO(b'abcd1234'))
        }

    You can also pass in the extra information as a JSON blob::

        {
            'extra': '{"ProductName":"Test","Version":"1.0"}',
        }

    You can also pass in file pointers for files::

        {
            'ProductName': 'Test',
            'Version': '1.0',
            'upload_file_minidump': ('fakecrash.dump', open('crash.dmp', 'rb'))
        }


    This returns a tuple of two things:

    1. a ``bytes`` object with the HTTP POST payload
    2. a dict of headers with ``Content-Type`` and ``Content-Length`` in it


    :arg params: Python dict of name -> value pairs. Values must be one of:

         1. strings,
         2. tuple of ``("extra.json", JSON blob as string)``
         3. tuple of ``(filename, file-like object with .read())``

    :arg boundary: The MIME boundary string to use. Otherwise this will be
        generated.

    :returns: tuple of (bytes, headers dict)

    """
    if boundary is None:
        boundary = uuid.uuid4().hex

    output = io.BytesIO()
    headers = {"Content-Type": "multipart/form-data; boundary=%s" % boundary}

    for key, val in sorted(raw_crash.items()):
        block = ["--%s" % boundary]

        if isinstance(val, (float, int, str)):
            if key == "extra":
                block.append(
                    'Content-Disposition: form-data; name="extra"; filename="extra.json"'
                )
                block.append("Content-Type: application/json")
            else:
                block.append(
                    'Content-Disposition: form-data; name="%s"' % Header(key).encode()
                )
                block.append("Content-Type: text/plain; charset=utf-8")
        elif isinstance(val, tuple):
            block.append(
                'Content-Disposition: form-data; name="%s"; filename="%s"'
                % ((Header(key).encode(), Header(val[0]).encode()))
            )
            block.append("Content-Type: application/octet-stream")
        else:
            logger.info("Skipping %r" % key)
            continue

        block.append("")
        block.append("")

        output.write("\r\n".join(block).encode("utf-8"))

        if isinstance(val, str):
            output.write(val.encode("utf-8"))
        elif isinstance(val, (float, int)):
            output.write(str(val).encode("utf-8"))
        else:
            output.write(val[1].read())

        output.write(b"\r\n")

    # Add end boundary and convert to bytes.
    output.write(("--%s--\r\n" % boundary).encode("utf-8"))
    output = output.getvalue()

    headers["Content-Length"] = str(len(output))

    return output, headers


def post_crash(url, crash_payload, compressed=False):
    """Posts a crash to specified url

    .. Note:: This is not full-featured. It's for testing purposes only.

    :arg str url: The url to post to.
    :arg dict crash_payload: The raw crash and dumps as a single thing.
    :arg bool compressed: Whether or not to post a compressed payload.

    :returns: The requests Response instance.

    """
    payload, headers = multipart_encode(crash_payload)

    logger.info("Posting crash of size %d" % len(payload))

    if compressed:
        payload = compress(payload)
        headers["Content-Encoding"] = "gzip"

    return requests.post(url, headers=headers, data=payload)


def get_json_data(fn):
    with open(fn, "r") as fp:
        return json.load(fp)


def cmdline(args):
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--url",
        dest="url",
        default="http://localhost:8000/submit",
        help="Submission url.",
    )
    parser.add_argument(
        "--compressed",
        dest="compressed",
        action="store_true",
        help="Whether or not to compress the HTTP payload.",
    )
    parser.add_argument(
        "--use-json",
        dest="use_json",
        action="store_true",
        help="Whether or not to put metadata in a single JSON blob value.",
    )
    parser.add_argument(
        "--raw_crash", dest="raw_crash", default="", help="Path to raw_crash JSON file."
    )
    parser.add_argument(
        "--dump",
        dest="dumps",
        action="append",
        help=(
            "This is in name:path form. You can have multple dumps, but they have to "
            "have different names."
        ),
    )
    parser.add_argument("--verbose", dest="verbose", action="store_true")
    parsed = parser.parse_args(args)

    print("URL:         %s" % parsed.url)
    print("Compressed?: %s" % parsed.compressed)
    print("Verbose?:    %s" % parsed.verbose)

    logging.basicConfig(level=logging.DEBUG)
    if parsed.verbose:
        _log_everything()

    url = parsed.url
    compressed = parsed.compressed
    use_json = parsed.use_json

    if parsed.raw_crash:
        logger.info("Using raw crash %s..." % parsed.raw_crash)
        raw_crash = json.load(open(parsed.raw_crash, "r"))

        # Remove this if it's there--it gets generated by the collector
        if "dump_checksums" in raw_crash:
            del raw_crash["dump_checksums"]

        # FIXME(willkg): Should we remove other things, too?

    else:
        logger.info("Generating crash...")
        # FIXME(willkg): Generate a crash here
        raw_crash = {"ProductName": "Firefox", "Version": "1"}

    dumps = {}
    if parsed.dumps:
        # If the user specified dump files to add, then add those.
        for dump in parsed.dumps:
            if ":" in dump:
                # This is name:path form
                dump_name, dump_path = dump.split(":")
            else:
                dump_name, dump_path = "upload_file_minidump", dump

            logger.info("Adding dump %s -> %s..." % (dump_name, dump_path))
            dumps[dump_name] = open(dump_path, "rb").read()

    elif "v2" in parsed.raw_crash:
        # If there's a 'v2' in the raw_crash filename, then it's probably the
        # case that willkg wants all the pieces for a crash he pulled from S3.
        # We like willkg, so we'll help him out by doing the legwork.
        raw_crash_path = Path(parsed.raw_crash)
        if str(raw_crash_path.parents[3]).endswith("v2"):
            logger.info("Trying to find dump_names and dumps...")
            crashid = str(Path(parsed.raw_crash).name)

            # First, raw_crash is ROOT/v2/raw_crash/ENTROPY/DATE/CRASHID, so
            # find the root.
            root_path = Path(parsed.raw_crash).parents[4]

            # First find dump_names which tells us about all the dumps.
            logger.info("Looking for dumps listed in dump_names...")
            dump_names_path = root_path / "v1" / "dump_names" / crashid
            dump_names = get_json_data(str(dump_names_path))

            for dump_name in dump_names:
                logger.info("Adding dump %s..." % dump_name)
                if dump_name == "upload_file_minidump":
                    fn = root_path / "v1" / "dump" / crashid
                else:
                    fn = root_path / "v1" / dump_name / crashid

                with open(str(fn), "rb") as fp:
                    data = fp.read()

                dumps[dump_name] = data

    logger.info("Assembling payload...")
    crash_payload = assemble_crash_payload_dict(
        raw_crash=raw_crash, dumps=dumps, use_json=use_json
    )

    if compressed:
        logger.info("Posting compressed crash report...")

    if use_json:
        logger.info("Sending metadata in single JSON field...")

    resp = post_crash(url=url, crash_payload=crash_payload, compressed=compressed)

    logger.info("Post response: %s %r" % (resp.status_code, resp.content))
    return 0


if __name__ == "__main__":
    sys.exit(cmdline(sys.argv[1:]))
