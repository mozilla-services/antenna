# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import hashlib
import io
import json
import logging
import time
from typing import Dict, List
import zlib

from attrs import define, field
from everett.manager import Option
import falcon
from falcon.media.multipart import (
    MultipartFormHandler,
    MultipartParseError,
    MultipartParseOptions,
)
import markus

from antenna.throttler import REJECT, FAKEACCEPT, RESULT_TO_TEXT, Throttler
from antenna.util import (
    create_crash_id,
    sanitize_key_name,
    utc_now,
    validate_crash_id,
)


logger = logging.getLogger(__name__)
mymetrics = markus.get_metrics("breakpad_resource")


#: Bad fields we should never save, so remove them from the payload before
#: they get any further
BAD_FIELDS = [
    "Email",
    "TelemetryClientId",
    "TelemetryServerURL",
    "TelemetrySessionId",
]


class MalformedCrashReport(Exception):
    """Exception raised when the crash report payload is malformed.

    Message should be an alpha-numeric error code with no spaces.

    """


@define
class CrashReport:
    annotations: Dict[str, str] = field(factory=dict)
    dumps: Dict[str, bytes] = field(factory=dict)
    notes: List[str] = field(factory=list)
    payload: str = "unknown"
    payload_compressed: str = "0"


class BreakpadSubmitterResource:
    """Handles incoming breakpad-style crash reports.

    This handles incoming HTTP POST requests containing breakpad-style crash reports in
    multipart/form-data format.

    It can handle compressed or uncompressed POST payloads.

    It parses the payload from the HTTP POST request, runs it through the throttler with
    the specified rules, generates a crash_id, returns the crash_id to the HTTP client,
    and passes the crash report data to the crashmover.

    """

    class Config:
        dump_field = Option(
            default="upload_file_minidump",
            doc="The name of the field in the POST data for dumps.",
        )

    def __init__(self, config, crashmover):
        self.config = config.with_options(self)
        self.crashmover = crashmover
        self.throttler = Throttler(config.with_namespace("throttler"))

        self._multipart_parse_options = MultipartParseOptions()
        # Setting this to 0 means "infinity"
        self._multipart_parse_options.max_body_part_count = 0
        # We set this to 20mb semi-arbitrarily; we can increase it as we need to
        self._multipart_parse_options.max_body_part_buffer_size = 20 * 1024 * 1024

    def get_components(self):
        """Return map of namespace -> component for traversing component tree."""
        return {"throttler": self.throttler}

    def extract_payload(self, req):
        """Parse HTTP POST payload.

        Decompresses the payload if necessary and then walks through the payload
        converting from ``multipart`` to Python datatypes.

        NOTE(willkg): The FieldStorage is poorly documented (in my opinion). It
        has a list attribute that is a list of FieldStorage items--one for each
        key/val in the form. For attached files, the FieldStorage will have a
        name, value and filename and the type should be
        ``application/octet-stream``. Thus we parse it looking for things of type
        ``text/plain``, ``application/json``, and ``application/octet-stream``.

        :arg falcon.request.Request req: a Falcon Request instance

        :returns: CrashReport

        :raises MalformedCrashReport:

        """
        # If we don't have a content type, raise MalformedCrashReport
        if not req.content_type:
            raise MalformedCrashReport("no_content_type")

        # If it's the wrong content type or there's no boundary section, raise
        # MalformedCrashReport
        content_type_parts = [part.strip() for part in req.content_type.split(";", 1)]
        if (
            len(content_type_parts) != 2
            or content_type_parts[0] not in ("multipart/form-data", "multipart/mixed")
            or not content_type_parts[1].startswith("boundary=")
        ):
            if content_type_parts[0] not in ("multipart/form-data", "multipart/mixed"):
                raise MalformedCrashReport("wrong_content_type")
            else:
                raise MalformedCrashReport("no_boundary")

        content_length = req.content_length or 0

        # If there's no content, raise MalformedCrashReport
        if content_length == 0:
            raise MalformedCrashReport("no_content_length")

        crash_report = CrashReport()

        # Decompress payload if it's compressed
        if req.env.get("HTTP_CONTENT_ENCODING") == "gzip":
            mymetrics.incr("gzipped_crash")
            crash_report.payload_compressed = "1"

            # If the content is gzipped, we pull it out and decompress it. We
            # have to do that here because nginx doesn't have a good way to do
            # that in nginx-land.
            gzip_header = 16 + zlib.MAX_WBITS
            start_time = time.perf_counter()
            try:
                data = zlib.decompress(req.stream.read(content_length), gzip_header)
                mymetrics.histogram(
                    "gzipped_crash_decompress",
                    value=(time.perf_counter() - start_time) * 1000.0,
                    tags=["result:success"],
                )
            except zlib.error:
                mymetrics.histogram(
                    "gzipped_crash_decompress",
                    value=(time.perf_counter() - start_time) * 1000.0,
                    tags=["result:fail"],
                )
                # This indicates this isn't a valid compressed stream. Given
                # that the HTTP request insists it is, we're just going to
                # assume it's junk and not try to process any further.
                raise MalformedCrashReport("bad_gzip")

            # Stomp on the content length to correct it because we've changed
            # the payload size by decompressing it. We save the original value
            # in case we need to debug something later on.
            req.env["ORIG_CONTENT_LENGTH"] = content_length
            content_length = len(data)
            req.env["CONTENT_LENGTH"] = str(content_length)

            data = io.BytesIO(data)
            mymetrics.histogram(
                "crash_size", value=content_length, tags=["payload:compressed"]
            )

        else:
            data = req.bounded_stream
            mymetrics.histogram(
                "crash_size", value=content_length, tags=["payload:uncompressed"]
            )

        has_json = False
        has_kvpairs = False

        # Create a form handler that has no max_body_part_count
        handler = MultipartFormHandler(parse_options=self._multipart_parse_options)
        try:
            form = handler.deserialize(
                stream=data,
                content_type=req.content_type,
                content_length=content_length,
            )

            for part in form:
                if not part.name:
                    # If the field has no name, then it's probably junk, so let's drop it.
                    continue

                if part.content_type.startswith("application/json"):
                    # This is a JSON blob, so load it and override raw_crash with
                    # it.
                    has_json = True
                    try:
                        annotations = json.loads(part.stream.read())
                    except (json.decoder.JSONDecodeError, UnicodeDecodeError):
                        # The UnicodeDecodeError can happen if the utf-8 codec can't decode
                        # one of the characters. The JSONDecodeError can happen in a variety
                        # of "malformed JSON" situations.
                        raise MalformedCrashReport("invalid_json")

                    if not isinstance(annotations, dict):
                        raise MalformedCrashReport("invalid_json_value")

                    crash_report.annotations = annotations

                elif part.content_type.startswith("text/plain") and not part.filename:
                    # This isn't a dump, so it's a key/val pair, so we add that as a string.
                    has_kvpairs = True
                    try:
                        crash_report.annotations[part.name] = part.get_text()
                    except MultipartParseError as mpe:
                        logger.error(
                            f"extract payload text part exception: {mpe.description}"
                        )
                        raise MalformedCrashReport("invalid_annotation_value") from mpe

                else:
                    if part.content_type != "application/octet-stream":
                        # FIXME(willkg): we should accumulate these issues and then toss
                        # them in the raw crash where we can see them better
                        logging.info(
                            f"unknown content type: {part.name} {part.content_type}"
                        )

                    # This is a dump, so add it to dumps using a sanitized dump name.
                    dump_name = sanitize_key_name(part.name)
                    crash_report.dumps[dump_name] = part.stream.read()

        except MultipartParseError as mpe:
            # If we hit this, then there are a few things that are likely wrong:
            #
            # 1. boundaries are missing or malformed
            # 2. missing EOL sequences
            # 3. file parts are missing Content-Type declaration
            logger.error(f"extract payload exception: {mpe.description}")
            raise MalformedCrashReport("invalid_payload_structure") from mpe

        if not crash_report.annotations:
            raise MalformedCrashReport("no_annotations")

        if has_json and has_kvpairs:
            # If the crash payload has both kvpairs and a JSON blob, then it's malformed
            # and we should dump it.
            raise MalformedCrashReport("has_json_and_kv")

        # Add a note about how the annotations were encoded in the crash report. For
        # now, there are two options: json and multipart.
        crash_report.payload = "json" if has_json else "multipart"

        return crash_report

    def get_throttle_result(self, raw_crash):
        """Run raw_crash through throttler for a throttling result.

        :arg dict raw_crash: the raw crash to throttle

        :returns tuple: ``(result, rule_name, percentage)``

        """
        # At this stage, nothing has given us a throttle answer, so we throttle the
        # crash.
        result, rule_name, throttle_rate = self.throttler.throttle(raw_crash)
        return result, rule_name, throttle_rate

    def cleanup_crash_report(self, raw_crash):
        """Remove anything from the crash report that shouldn't be there.

        This operates on the raw_crash in-place. This adds notes to ``collector_notes``.

        """
        if "metadata" not in raw_crash:
            raw_crash["metadata"] = {}

        notes = raw_crash["metadata"].setdefault("collector_notes", [])

        # Remove bad fields
        for bad_field in BAD_FIELDS:
            if bad_field in raw_crash:
                del raw_crash[bad_field]
                notes.append("Removed %s from raw crash." % bad_field)

    @mymetrics.timer_decorator("on_post.time")
    def on_post(self, req, resp):
        """Handle incoming HTTP POSTs.

        Note: This is executed by the WSGI app, so it and anything it does is
        covered by the Sentry middleware.

        """
        resp.status = falcon.HTTP_200

        current_timestamp = utc_now()

        # NOTE(willkg): This has to return text/plain since that's what the
        # breakpad clients expect.
        resp.content_type = "text/plain"

        try:
            crash_report = self.extract_payload(req)

        except MalformedCrashReport as exc:
            # If this is malformed, then reject it with malformed error code.
            msg = str(exc)
            mymetrics.incr("malformed", tags=["reason:%s" % msg])
            resp.status = falcon.HTTP_400
            resp.text = "Discarded=malformed_%s" % msg
            return

        mymetrics.incr("incoming_crash")

        raw_crash = crash_report.annotations

        # Add timestamp to crash report
        raw_crash["submitted_timestamp"] = current_timestamp.isoformat()

        # Add metadata
        raw_crash["metadata"] = {
            "payload": crash_report.payload,
            "payload_compressed": crash_report.payload_compressed,
            "collector_notes": [],
        }

        # Add checksums to metadata
        raw_crash["metadata"]["dump_checksums"] = {
            dump_name: hashlib.sha256(dump).hexdigest()
            for dump_name, dump in crash_report.dumps.items()
        }

        # Add version information
        raw_crash["version"] = 2

        # First throttle the crash which gives us the information we need
        # to generate a crash id.
        throttle_result, rule_name, percentage = self.get_throttle_result(raw_crash)

        # Use a uuid if they gave us one and it's valid--otherwise create a new
        # one.
        if "uuid" in raw_crash and validate_crash_id(raw_crash["uuid"]):
            crash_id = raw_crash["uuid"]
            logger.info("%s has existing crash_id", crash_id)

        else:
            crash_id = create_crash_id(
                timestamp=current_timestamp, throttle_result=throttle_result
            )
            raw_crash["uuid"] = crash_id

        # Log the throttle result
        logger.info(
            "%s: matched by %s; returned %s",
            crash_id,
            rule_name,
            RESULT_TO_TEXT[throttle_result],
        )
        mymetrics.incr("throttle_rule", tags=["rule:%s" % rule_name])
        mymetrics.incr(
            "throttle", tags=["result:%s" % RESULT_TO_TEXT[throttle_result].lower()]
        )

        # If the result is REJECT, then discard it
        if throttle_result is REJECT:
            resp.text = "Discarded=rule_%s" % rule_name
            return

        # If the result is a FAKEACCEPT, then we return a crash id, but throw the crash
        # away
        if throttle_result is FAKEACCEPT:
            resp.text = "CrashID=bp-%s\n" % crash_id
            return

        # If we're accepting the cash report, then clean it up, save it and return the
        # CrashID to the client
        self.cleanup_crash_report(raw_crash)

        # Add crash report to crashmover queue
        self.crashmover.add_crashreport(
            raw_crash=raw_crash, dumps=crash_report.dumps, crash_id=crash_id
        )

        resp.text = "CrashID=bp-%s\n" % crash_id
