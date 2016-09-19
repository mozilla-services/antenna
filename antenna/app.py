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
from everett.component import ConfigOptions, RequiredConfigMixin
import falcon

from antenna.lib.datetimeutil import utc_now
from antenna.lib.ooid import create_new_ooid
from antenna.util import de_null


logger = logging.getLogger('gunicorn.error')


class BreakpadSubmitterResource(RequiredConfigMixin):
    """Handles incoming breakpad crash reports and saves to S3"""
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
        default='antenna.external.boto.crashstorage.BotoS3CrashStorage',
        parser=parse_class,
        doc='the class in charge of storing crashes'
    )

    def __init__(self, config):
        self.config = config.with_options(self)
        self.crashstorage = self.config('crashstorage_class')(config)

    def process_fieldstorage(self, fs):
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

           * FieldStorage('upload_file_minidump', 'fakecrash.dump', b'abcd1234')

        3. It's a FieldStorage with name and filename as None, and the value is
           a list of FieldStorage items.

           * FieldStorage(None, None, [FieldStorage('ProductName', ...)...])

        This method converts that into a structure of Python simple types.

        """
        if isinstance(fs, cgi.FieldStorage):
            if fs.name is None and fs.filename is None:
                return dict(
                    [(key, self.process_fieldstorage(fs[key])) for key in fs]
                )
            else:
                # Note: The old code never kept the filename around and this
                # doesn't either.
                return fs.value
        else:
            return fs

    def extract_payload(self, req):
        """Parses the HTTP POST payload

        Decompresses the payload if necessary and then walks through the
        payload converting from multipart/form-data to Python datatypes.

        :arg req: a Falcon Request instance

        :returns: (raw_crash dict, dumps dict)

        """
        # Decompress payload if it's compressed
        if req.env.get('HTTP_CONTENT_ENCODING') == 'gzip':
            # If the content is gzipped, we pull it out and decompress it. We
            # have to do that here because nginx doesn't have a good way to do
            # that in nginx-land.
            gzip_header = 16 + zlib.MAX_WBITS
            content_length = int(req.env.get('CONTENT_LENGTH', 0))
            data = zlib.decompress(
                req.stream.read(content_length), gzip_header
            )
            # Stomp on the content length to correct it because we've changed
            # the payload size by decompressing it. We save the original value
            # in case we need to debug something later on.
            req.env['ORIG_CONTENT_LENGTH'] = content_length
            req.env['CONTENT_LENGTH'] = len(data)

            data = io.BytesIO(data)
        else:
            data = req.stream

        # Convert to FieldStorage and then to dict
        fs = cgi.FieldStorage(fp=data, environ=req.env, keep_blank_values=1)
        payload = self.process_fieldstorage(fs)

        # NOTE(willkg): In the original collector, this returned request
        # querystring data as well as request body data, but we're not doing
        # that because the query string just duplicates data in the payload.

        raw_crash = {}
        dumps = {}

        # FIXME(willkg): I think this has extra stanzas it doesn't need. Pretty
        # sure payload items are either strings or bytes and that's it. I threw
        # some asserts in there that will fail immediately, so if we ever bump
        # into it, we'll know. This should reveal itself in testing. If it
        # never pops up, we can nix the sections.
        for key, val in payload.items():
            if isinstance(val, str):
                if key != 'dump_checksums':
                    raw_crash[key] = de_null(val)
                else:
                    assert False, 'string with key == dump_checksums'

            elif isinstance(val, int):
                assert False, 'can be an int'
                raw_crash[key] = val

            elif isinstance(val, bytes):
                dumps[key] = val
                checksum = hashlib.md5(val).hexdigest()
                raw_crash.setdefault('dump_checksums', {})[key] = checksum

            else:
                assert False, 'can be something other than str, int or bytes'
                raw_crash[key] = val.value

        return raw_crash, dumps

    def on_post(self, req, resp):
        resp.content_type = 'text/plain'

        raw_crash, dumps = self.extract_payload(req)

        current_timestamp = utc_now()
        raw_crash['submitted_timestamp'] = current_timestamp.isoformat()
        # FIXME(willkg): Check the processor to see if we can remove this.
        raw_crash['timestamp'] = time.time()

        if 'uuid' not in raw_crash:
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

        raw_crash['type_tag'] = self.config('dump_id_prefix').strip('-')

        self.crashstorage.save_raw_crash(
            raw_crash,
            dumps,
            crash_id
        )
        logger.info('%s accepted', crash_id)

        resp.status = falcon.HTTP_200
        resp.body = 'CrashID=%s%s\n' % (self.config('dump_id_prefix'), crash_id)


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
