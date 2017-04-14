# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import cgi
from collections import deque, namedtuple
import hashlib
import io
import logging
import time
import zlib

from everett.component import ConfigOptions, RequiredConfigMixin
from everett.manager import parse_class
import falcon
from falcon.request_helpers import BoundedStream
from gevent.pool import Pool

from antenna import metrics
from antenna.heartbeat import register_for_life, register_for_heartbeat
from antenna.sentry import capture_unhandled_exceptions
from antenna.throttler import (
    ACCEPT,
    DEFER,
    REJECT,
    RESULT_TO_TEXT,
    Throttler,
)
from antenna.util import (
    create_crash_id,
    de_null,
    utc_now,
)


logger = logging.getLogger(__name__)
mymetrics = metrics.get_metrics('breakpad_resource')


CrashReport = namedtuple('CrashReport', ['raw_crash', 'dumps', 'crash_id'])


def positive_int(val):
    """Everett parser that enforces val >= 1"""
    val = int(val)
    if val < 1:
        raise ValueError('val must be greater than 1: %s' % val)
    return val


class BreakpadSubmitterResource(RequiredConfigMixin):
    """Handles incoming breakpad crash reports and saves to crashstorage

    This handles incoming HTTP POST requests containing breakpad-style crash
    reports in multipart/form-data format.

    It can handle compressed or uncompressed POST payloads.

    It parses the payload from the HTTP POST request, runs it through the
    throttler with the specified rules, generates a crash_id, returns the
    crash_id to the HTTP client and then saves the crash using the configured
    crashstorage class.

    .. Note::

       From when a crash comes in to when it's saved by the crashstorage class,
       the crash is entirely in memory. Keep that in mind when figuring out
       how to scale your Antenna nodes.


    The most important configuration bit here is choosing the crashstorage
    class.

    For example::

        CRASHSTORAGE_CLASS=antenna.ext.s3.crashstorage.S3CrashStorage

    """
    required_config = ConfigOptions()
    required_config.add_option(
        'dump_field', default='upload_file_minidump',
        doc='the name of the field in the POST data for dumps'
    )
    required_config.add_option(
        'dump_id_prefix', default='bp-',
        doc='the crash type prefix'
    )
    required_config.add_option(
        'crashstorage_class',
        default='antenna.ext.crashstorage_base.NoOpCrashStorage',
        parser=parse_class,
        doc='the class in charge of storing crashes'
    )

    # Maximum number of concurrent crashmover workers; each process gets this
    # many concurrent crashmovers, so if you're running 5 processes on the node
    # then it's (5 * concurrent_crashmovers) fighting for upload bandwidth
    required_config.add_option(
        'concurrent_crashmovers',
        default='2',
        parser=int,
        doc='the number of crashes concurrently being saved to s3'
    )

    def __init__(self, config):
        self.config = config.with_options(self)
        self.crashstorage = self.config('crashstorage_class')(config.with_namespace('crashstorage'))
        self.throttler = Throttler(config)

        # Gevent pool for crashmover workers
        self.crashmover_pool = Pool(size=self.config('concurrent_crashmovers'))

        # Queue for crashmover of crashes to save
        self.crashmover_save_queue = deque()

        # Register hb functions with heartbeat manager
        register_for_heartbeat(self.hb_report_health_stats)
        register_for_heartbeat(self.hb_run_crashmover)

        # Register life function with heartbeat manager
        register_for_life(self.has_work_to_do)

    def get_runtime_config(self, namespace=None):
        for item in super().get_runtime_config():
            yield item

        for item in self.throttler.get_runtime_config():
            yield item

        for item in self.crashstorage.get_runtime_config(['crashstorage']):
            yield item

    def check_health(self, state):
        if hasattr(self.crashstorage, 'check_health'):
            self.crashstorage.check_health(state)

    def hb_report_health_stats(self):
        # The number of crash reports sitting in the queue; this is a direct
        # measure of the health of this process--a number that's going up means
        # impending doom
        mymetrics.gauge('save_queue_size', len(self.crashmover_save_queue))

    def has_work_to_do(self):
        work_to_do = len(self.crashmover_save_queue) + len(self.crashmover_pool)
        logger.info('work left to do: %s' % work_to_do)
        # Indicates whether or not we're sitting on crashes to save--this helps
        # keep Antenna alive until we're done saving crashes
        return bool(work_to_do)

    def extract_payload(self, req):
        """Parses the HTTP POST payload

        Decompresses the payload if necessary and then walks through the
        FieldStorage converting from multipart/form-data to Python datatypes.

        NOTE(willkg): The FieldStorage is poorly documented (in my opinion). It
        has a list attribute that is a list of FieldStorage items--one for each
        key/val in the form. For attached files, the FieldStorage will have a
        name, value and filename and the type should be
        application/octet-stream. Thus we parse it looking for things of type
        text/plain and application/octet-stream.

        :arg req: a Falcon Request instance

        :returns: (raw_crash dict, dumps dict)

        """
        # If we don't have a content type, return an empty crash
        if not req.content_type:
            return {}, {}

        # If it's the wrong content type or there's no boundary section, return
        # an empty crash
        content_type = [part.strip() for part in req.content_type.split(';', 1)]
        if ((len(content_type) != 2 or
             content_type[0] != 'multipart/form-data' or
             not content_type[1].startswith('boundary='))):
            return {}, {}

        content_length = req.content_length or 0

        # If there's no content, return an empty crash
        if content_length == 0:
            return {}, {}

        # Decompress payload if it's compressed
        if req.env.get('HTTP_CONTENT_ENCODING') == 'gzip':
            mymetrics.incr('gzipped_crash')

            # If the content is gzipped, we pull it out and decompress it. We
            # have to do that here because nginx doesn't have a good way to do
            # that in nginx-land.
            gzip_header = 16 + zlib.MAX_WBITS
            try:
                data = zlib.decompress(req.stream.read(content_length), gzip_header)
            except zlib.error:
                # This indicates this isn't a valid compressed stream. Given
                # that the HTTP request insists it is, we're just going to
                # assume it's junk and not try to process any further.
                mymetrics.incr('bad_gzipped_crash')
                return {}, {}

            # Stomp on the content length to correct it because we've changed
            # the payload size by decompressing it. We save the original value
            # in case we need to debug something later on.
            req.env['ORIG_CONTENT_LENGTH'] = content_length
            content_length = len(data)
            req.env['CONTENT_LENGTH'] = str(content_length)

            data = io.BytesIO(data)
            mymetrics.histogram('crash_size.compressed', content_length)
        else:
            # NOTE(willkg): At this point, req.stream is either a
            # falcon.request_helper.BoundedStream (in tests) or a
            # gunicorn.http.body.Body (in production).
            #
            # FieldStorage doesn't work with BoundedStream so we pluck out the
            # internal stream from that which works fine.
            #
            # FIXME(willkg): why don't tests work with BoundedStream?
            if isinstance(req.stream, BoundedStream):
                data = req.stream.stream
            else:
                data = req.stream

            mymetrics.histogram('crash_size.uncompressed', content_length)

        fs = cgi.FieldStorage(fp=data, environ=req.env, keep_blank_values=1)

        # NOTE(willkg): In the original collector, this returned request
        # querystring data as well as request body data, but we're not doing
        # that because the query string just duplicates data in the payload.

        raw_crash = {}
        dumps = {}

        for fs_item in fs.list:
            if fs_item.name == 'dump_checksums':
                # We don't want to pick up the dump_checksums from a raw
                # crash that was re-submitted.
                continue

            elif fs_item.type and (fs_item.type.startswith('application/octet-stream') or isinstance(fs_item.value, bytes)):
                # This is a dump, so we get a checksum and save the bits in the
                # relevant places.

                # FIXME(willkg): The dump name is essentially user-provided. We should
                # sanitize it before proceeding.
                dumps[fs_item.name] = fs_item.value
                checksum = hashlib.md5(fs_item.value).hexdigest()
                raw_crash.setdefault('dump_checksums', {})[fs_item.name] = checksum

            else:
                # This isn't a dump, so it's a key/val pair, so we add that.
                raw_crash[fs_item.name] = de_null(fs_item.value)

        return raw_crash, dumps

    def get_throttle_result(self, raw_crash):
        """Given a raw_crash, figures out the throttling

        If the raw_crash contains throttling information already, it returns
        that. If it doesn't, then this will apply throttling and return the
        results of that.

        A rule name of ``ALREADY_THROTTLED`` indicates that the raw_crash was
        previously throttled and we're re-using that data.

        A rule name of ``THROTTLEABLE_0`` indicates that the raw_crash was
        marked to not be throttled.

        :arg dict raw_crash: the raw crash to throttle

        :returns tuple: ``(result, rule_name, percentage)``

        """
        # If the raw_crash has a uuid, then that implies throttling, so return
        # that.
        if 'uuid' in raw_crash:
            crash_id = raw_crash['uuid']
            if int(crash_id[-7]) in (ACCEPT, DEFER):
                result = int(crash_id[-7])
                throttle_rate = 100

                # Save the results in the raw_crash itself
                raw_crash['legacy_processing'] = result
                raw_crash['throttle_rate'] = throttle_rate

                return result, 'FROM_CRASHID', throttle_rate

        # If we have throttle results for this crash, return those.
        if 'legacy_processing' in raw_crash and 'throttle_rate' in raw_crash:
            try:
                result = int(raw_crash['legacy_processing'])
                if result not in (ACCEPT, DEFER):
                    raise ValueError('Result is not a valid value: %r', result)

                throttle_rate = int(raw_crash['throttle_rate'])
                if not (0 <= throttle_rate <= 100):
                    raise ValueError('Throttle rate is not a valid value: %r', result)
                return result, 'ALREADY_THROTTLED', throttle_rate

            except ValueError:
                # If we've gotten a ValueError, it means one or both of the
                # values is bad and we should ignore it and move forward.
                mymetrics.incr('throttle.bad_throttle_values')

        # If we have a Throttleable=0, then return that.
        if raw_crash.get('Throttleable', None) == '0':
            # If the raw crash has ``Throttleable=0``, then we accept the
            # crash.
            mymetrics.incr('throttleable_0')
            result = ACCEPT
            rule_name = 'THROTTLEABLE_0'
            throttle_rate = 100

        else:
            # At this stage, nothing has given us a throttle answer, so we
            # throttle the crash.
            result, rule_name, throttle_rate = self.throttler.throttle(raw_crash)

        # Save the results in the raw_crash itself
        raw_crash['legacy_processing'] = result
        raw_crash['throttle_rate'] = throttle_rate

        return result, rule_name, throttle_rate

    @mymetrics.timer_decorator('on_post.time')
    def on_post(self, req, resp):
        """Handles incoming HTTP POSTs

        Note: This is executed by the WSGI app, so it and anything it does is
        covered by the Sentry middleware.

        """
        resp.status = falcon.HTTP_200

        start_time = time.time()
        resp.content_type = 'text/plain'

        raw_crash, dumps = self.extract_payload(req)

        # If we didn't get any crash data, then just drop it and move on--don't
        # count this as an incoming crash and don't do any more work on it
        if not raw_crash:
            resp.body = 'Discarded=1'
            return

        mymetrics.incr('incoming_crash')

        current_timestamp = utc_now()
        raw_crash['submitted_timestamp'] = current_timestamp.isoformat()
        raw_crash['timestamp'] = start_time

        # First throttle the crash which gives us the information we need
        # to generate a crash id.
        throttle_result, rule_name, percentage = self.get_throttle_result(raw_crash)

        if 'uuid' in raw_crash:
            # FIXME(willkg): This means the uuid is essentially user-provided.
            # We should sanitize it before proceeding.
            crash_id = raw_crash['uuid']
            logger.info('%s has existing crash_id', crash_id)

        else:
            crash_id = create_crash_id(
                timestamp=current_timestamp,
                throttle_result=throttle_result
            )
            raw_crash['uuid'] = crash_id

        raw_crash['type_tag'] = self.config('dump_id_prefix').strip('-')

        # Log the throttle result
        logger.info('%s: matched by %s; returned %s', crash_id, rule_name,
                    RESULT_TO_TEXT[throttle_result])
        mymetrics.incr(('throttle.%s' % RESULT_TO_TEXT[throttle_result]).lower())

        if throttle_result is REJECT:
            # If the result is REJECT, then discard it
            resp.body = 'Discarded=1'

        else:
            # If the result is not REJECT, then save it and return the CrashID
            # to the client
            self.crashmover_save_queue.append(CrashReport(raw_crash, dumps, crash_id))
            self.hb_run_crashmover()
            resp.body = 'CrashID=%s%s\n' % (self.config('dump_id_prefix'), crash_id)

    def hb_run_crashmover(self):
        """Checks to see if it should spawn a crashmover and does if appropriate"""
        # Spawn a new crashmover if there's stuff in the queue and there isn't
        # one currently running
        if self.crashmover_save_queue and self.crashmover_pool.free_count() > 0:
            self.crashmover_pool.spawn(self.crashmover_process_queue)

    def crashmover_process_queue(self):
        """Processes the queue of crashes to save until it's empty

        Note: Since this is spawned, it happens in its own execution context
        outside of WSGI app HTTP request handling, so unhandled exceptions
        aren't captured by the Sentry WSGI middleware. Thus this creates its
        own capture context.

        Note: This has to be super careful not to lose crash reports. If
        there's any kind of problem, this must return the crash to the queue.

        """
        # Process crashes until the queue is empty
        while self.crashmover_save_queue:
            crash_report = self.crashmover_save_queue.popleft()
            try:
                with capture_unhandled_exceptions():
                    self.crashmover_save(crash_report)

            except Exception:
                logger.exception('Exception when processing save queue')
                mymetrics.incr('save_crash_exception.count')
                self.crashmover_save_queue.append(crash_report)

    def crashmover_save(self, crash_report):
        """Saves a crash to storage

        If this raises an error, then that bubbles up and the caller can figure
        out what to do with it and retry again later.

        """
        crash_id = crash_report.crash_id
        dumps = crash_report.dumps
        raw_crash = crash_report.raw_crash

        # Capture total time it takes to save the crash
        with mymetrics.timer('crash_save.time'):
            # Save dumps to crashstorage
            self.crashstorage.save_dumps(crash_id, dumps)

            # Save the raw crash metadata to crashstorage
            self.crashstorage.save_raw_crash(crash_id, raw_crash)

        # Capture the total time it took for this crash to be handled from
        # being received from breakpad client to saving to s3.
        #
        # NOTE(willkg): time.time returns seconds, but .timing() wants
        # milliseconds, so we multiply!
        delta = (time.time() - raw_crash['timestamp']) * 1000
        mymetrics.timing('crash_handling.time', delta)

        mymetrics.incr('save_crash.count')
        logger.info('%s saved', crash_id)

    def join_pool(self):
        """Joins the pool--use only in tests!

        This is helpful for forcing all the coroutines in the pool to complete
        so that we can verify outcomes in the test suite for work that might
        cross coroutines.

        """
        self.crashmover_pool.join()
