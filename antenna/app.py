# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import cgi
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


# FIXME: Figure out whether we need to implement this or nix it. For now, we're
# just going to define it as a synonym.
MemoryDumpsMapping = dict


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
        """Recursively works through a field storage converting to Python structure"""
        if isinstance(fs, dict):
            return dict(
                [(de_null(key), self._process_fieldstorage(fs[key])) for key in fs.keys()]
            )
        elif isinstance(fs, list):
            return [self._process_fieldstorage(x) for x in fs]
        elif fs.filename is None:
            return de_null(fs.value)
        else:
            return de_null(fs)

    def _extract_payload(self, req):
        """Extracts payload from request; returns dict

        Decompresses the payload if necessary. Converts from multipart form to
        Python dict and returns that.

        :arg req: the WSGI request

        :returns: dict structure

        """
        # Decompress payload if it's compressed
        # FIXME: Move this section to middleware?
        if req.env.get('HTTP_CONTENT_ENCODING') == 'gzip':
            # If the content is gzipped, we pull it out and decompress it. We
            # have to do that here because nginx doesn't have a good way to do
            # that in nginx-land.
            gzip_header = 16 + zlib.MAX_WBITS
            content_length = req.env.get(int('CONTENT_LENGTH'), 0)
            data = zlib.decompress(
                req.stream.read(content_length), gzip_header
            )
            data = io.StringIO(data)

        else:
            data = req.stream

        # Convert to FieldStorage and then to dict
        fs = cgi.FieldStorage(fp=data, environ=req.env.copy(), keep_blank_values=1)
        payload = self._process_fieldstorage(fs)

        # FIXME: In the original collector, this returned request querystring
        # data as well as request body data.

        return payload

    def on_post(self, req, resp):
        # FIXME: verify HTTP content type header for post?

        resp.content_type = 'text/plain'

        # Generate a crash id.
        current_timestamp = utc_now()
        crash_id = create_new_ooid(current_timestamp)

        # FIXME: Handle existing crash id case

        # FIXME: Add the following to the crash report:
        #
        # * "timestamp" - current_timestamp.isoformat()
        # * "submitted_timestamp" - current_timestamp in milliseconds (legacy--can we remove?)
        # * "type_tag" - "bp"
        # * "uuid" - crash id
        # * "legacy_processing" - the throttle result enumeration int
        # * "throttle_rate" - also from throttling

        raw_crash, dumps = self._get_raw_crash_from_form(req)

        raw_crash['submitted_timestamp'] = current_timestamp.isoformat()
        # legacy - ought to be removed someday
        raw_crash['timestamp'] = time.time()

        if not self.accept_submitted_crash_id or 'uuid' not in raw_crash:
            raw_crash['uuid'] = crash_id
            logger.info('%s received', crash_id)
        else:
            crash_id = raw_crash['uuid']
            logger.info('%s received with existing crash_id:', crash_id)

        # if ('legacy_processing' not in raw_crash or
        #         not self.accept_submitted_legacy_processing):

        #     raw_crash['legacy_processing'], raw_crash['throttle_rate'] = (
        #         self.throttler.throttle(raw_crash)
        #     )
        # else:
        #     raw_crash['legacy_processing'] = int(
        #         raw_crash['legacy_processing']
        #     )

        # if raw_crash['legacy_processing'] == DISCARD:
        #     logger.info('%s discarded', crash_id)
        #     resp.data = 'Discarded=1\n'
        #     return
        # if raw_crash['legacy_processing'] == IGNORE:
        #     logger.info('%s ignored', crash_id)
        #     resp.data = 'Unsupported=1\n'
        #     return

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
