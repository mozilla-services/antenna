# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import cgi
import hashlib
import io
import json
import logging
import time
import zlib

from everett.manager import ConfigManager, ConfigOSEnv, parse_class
import falcon

from antenna.lib.datetimeutil import utc_now
from antenna.lib.ooid import create_new_ooid
from antenna.lib.storage import Storage
from antenna.throttler import DISCARD, IGNORE
from antenna.util import de_null


logger = logging.getLogger('gunicorn.error')


class BreakpadSubmitterResource(object):
    def __init__(self, config):
        # the default name for the main dump
        self.dump_field = config(
            'dump_field', default='upload_file_minidump'
        )

        # the prefix to return to the client in front of the OOID
        self.dump_id_prefix = config(
            'dump_id_prefix', default='bp-'
        )

        # a boolean telling the collector to use a legacy_processing flag
        # submitted with the crash
        self.accept_submitted_legacy_processing = config(
            'accept_submitted_legacy_processing', default='False', parser=bool
        )

        # a boolean telling the collector to use a crash_id provided in the
        # crash submission
        self.accept_submitted_crash_id = config(
            'accept_submitted_crash_id', default='False', parser=bool
        )

        # a reference to method that accepts a string and calculates a hash
        # value
        self.checksum_method = config(
            'checksum_method', default='hashlib.md5', parser=parse_class
        )

        # class that implements the throttling action
        self.throttler = config(
            'throttler_class', default='antenna.throttler.Throttler',
            parser=parse_class
        )
        self.throttler = self.throttler(config)

        # source storage class
        self.crash_storage = config(
            'crashstorage_class',
            default='antenna.external.boto.crashstorage.BotoS3CrashStorage',
            parser=parse_class
        )
        self.crash_storage = self.crash_storage(config)

    def _process_fieldstorage(self, fs):
        """Recursively works through a field storage converting to Python structure

        FieldStorage can have a name, filename and a value. Thus we have the
        following possibilities:

        1. It's a FieldStorage with a name and a value.

           This is a regular form key/val pair. The value can be a str or an
           int.

           Example:

           * FieldStorage('ProductName', None, 'Test')

        2. It's a FieldStorage with a name, filename and value.

           This is a file. The value is bytes.

           * FieldStorage('upload_file_minidump', 'fakecrash.dump', b'abcd1234\n')

        3. It's a FieldStorage with name and filename as None, and the value is
           a list of FieldStorage items.

           * FieldStorage(None, None, [FieldStorage('ProductName', ...)...])

        This method converts that into a structure of Python simple types.

        """
        if isinstance(fs, cgi.FieldStorage):
            if fs.name is None and fs.filename is None:
                return dict(
                    [(key, self._process_fieldstorage(fs[key])) for key in fs]
                )
            else:
                # Note: The old code never kept he filename around and this
                # doesn't either.
                return fs.value
        else:
            return fs

    def extract_payload(self, req):
        """Extracts payload from request; returns dict

        Decompresses the payload if necessary. Converts from multipart form to
        Python dict and returns that.

        :arg req: the WSGI request

        :returns: dict structure

        """
        # Decompress payload if it's compressed
        # FIXME(willkg): Move this section to middleware?
        if req.env.get('HTTP_CONTENT_ENCODING') == 'gzip':
            # If the content is gzipped, we pull it out and decompress it. We
            # have to do that here because nginx doesn't have a good way to do
            # that in nginx-land.
            gzip_header = 16 + zlib.MAX_WBITS
            content_length = req.env.get(int('CONTENT_LENGTH'), 0)
            data = zlib.decompress(
                req.stream.read(content_length), gzip_header
            )
            data = io.BytesIO(data)

        else:
            data = req.stream

        # Convert to FieldStorage and then to dict
        fs = cgi.FieldStorage(fp=data, environ=req.env, keep_blank_values=1)
        payload = self._process_fieldstorage(fs)

        # NOTE(willkg): In the original collector, this returned request
        # querystring data as well as request body data, but we're not doing
        # that because the query string just duplicates data in the payload.

        raw_crash = {}
        dumps = {}

        # FIXME(willkg): I think this has extra stanzas it doesn't need.
        for key, val in payload.items():
            if isinstance(val, str):
                if key != 'dump_checksums':
                    raw_crash[key] = de_null(val)
                else:
                    print('OMG! not a string?')
            elif isinstance(val, int):
                print('INT')
                raw_crash[key] = val

            elif isinstance(val, bytes):
                dumps[key] = val
                checksum = hashlib.md5(val).hexdigest()
                raw_crash.setdefault('dump_checksums', {})[key] = checksum

            else:
                print('ELSE CLAUSE')
                raw_crash[key] = val.value

        return raw_crash, dumps

    def on_post(self, req, resp):
        # FIXME(willkg): verify HTTP content type header for post?

        resp.content_type = 'text/plain'

        # FIXME(willkg): Add the following to the crash report:
        #
        # * "timestamp" - current_timestamp.isoformat()
        # * "submitted_timestamp" - current_timestamp in milliseconds (legacy--can we remove?)
        # * "type_tag" - "bp"
        # * "uuid" - crash id
        # * "legacy_processing" - the throttle result enumeration int
        # * "throttle_rate" - also from throttling

        raw_crash, dumps = self.extract_payload(req)

        current_timestamp = utc_now()
        raw_crash['submitted_timestamp'] = current_timestamp.isoformat()
        # FIXME(willkg): Check to see if we can remove this.
        raw_crash['timestamp'] = time.time()

        if not self.accept_submitted_crash_id or 'uuid' not in raw_crash:
            crash_id = create_new_ooid(current_timestamp)
            raw_crash['uuid'] = crash_id
            logger.info('%s received', crash_id)
        else:
            crash_id = raw_crash['uuid']
            logger.info('%s received with existing crash_id:', crash_id)

        # NOTE(willkg): The old collector add "legacy_processing" and
        # "throttle_rate" which come from throttling. The new collector doesn't
        # throttle, so that gets added by the processor.

        # FIXME(willkg): The processor should only throttle *new* crashes
        # and not crashes coming into the priority or reprocessing queues.

        raw_crash['type_tag'] = self.dump_id_prefix.strip('-')

        self.crash_storage.save_raw_crash(
            raw_crash,
            dumps,
            crash_id
        )
        # logger.info('%s accepted', crash_id)

        resp.status = falcon.HTTP_200
        resp.body = 'CrashID=%s%s\n' % (self.dump_id_prefix, crash_id)


class HealthCheckResource(object):
    def __init__(self, config):
        self.config = config

    def on_get(self, req, resp):
        resp.content_type = 'application/json; charset=utf-8'

        # FIXME: This should query all the subsystems/components/whatever and
        # provide data from them. We need a registration system or something to
        # facilitate that programmatically.
        #
        # Once we know how everything is doing, we can determine the proper
        # status code. For now, 200 is fine.
        resp.status = falcon.HTTP_200
        resp.body = json.dumps({
            'health': 'v1',
        })


def get_app(config=None):
    """Returns AntennaAPI instance"""
    if config is None:
        config = ConfigManager([ConfigOSEnv()])
    app = falcon.API()
    app.add_route('/api/v1/health', HealthCheckResource(config))
    app.add_route('/submit', BreakpadSubmitterResource(config))
    return app
