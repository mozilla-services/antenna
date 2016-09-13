# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import base64
import cgi
import io
import json
import logging
import time
import zlib
from functools import wraps

from everett.manager import ConfigManager, ConfigOSEnv, parse_class
import falcon

from antenna.lib.datetimeutil import utc_now
from antenna.lib.ooid import create_new_ooid
from antenna.lib.storage import Storage
from antenna.throttler import DISCARD, IGNORE

logger = logging.getLogger('gunicorn.error')


def require_basic_auth(fun):
    """Decorator for requiring HTTP basic auth

    This is used in resources and requires the resource to have
    ``is_valid_auth`` implemented.

    Example::

        class HealthCheckResource:
            def is_valid_auth(self, username, password):
                return (username, password) == ('foo', 'bar')

            @require_basic_auth
            def on_get(self, req, resp):
                ...

    """
    def auth_error():
        raise falcon.HTTPUnauthorized(
            'Authentication required',
            'Authentication required',
            ['Basic']
        )

    @wraps(fun)
    def view_fun(resource, req, resp, *args, **kwargs):
        auth = req.auth
        if not auth:
            auth_error()

        auth = auth.strip()
        parts = auth.split(' ')
        if len(parts) != 2 or parts[0].lower().strip() != 'basic':
            auth_error()

        creds = base64.b64decode(parts[1]).split(':', 1)
        if not resource.is_valid_auth(creds[0], creds[1]):
            auth_error()

        return fun(resource, req, resp, *args, **kwargs)
    return view_fun


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
        # Note: Copied from web.py.
        if isinstance(fs, list):
            return [self._process_fieldstorage(x) for x in fs]
        elif fs.filename is None:
            return fs.value
        else:
            return fs

    def _form_as_mapping(self, req):
        """Extracts POST form data from request

        This handles gzip compressed form post data, too.

        :arg req: the WSGI request

        :returns: Storage instance with the data

        """
        if req.env.get('HTTP_CONTENT_ENCODING') == 'gzip':
            # If the content is gzipped, we pull it out and decompress it. We
            # have to do that here because nginx doesn't have a good way to do
            # that in nginx-land.
            gzip_header = 16 + zlib.MAX_WBITS
            content_length = req.env.get(int('CONTENT_LENGTH'), 0)
            data = zlib.decompress(
                req.stream.read(content_length), gzip_header
            )
            data = cStringIO.StringIO(data)

        else:
            data = req.stream

        env = req.env.copy()
        fs = cgi.FieldStorage(fp=data, environ=env, keep_blank_values=1)
        form = Storage(
            [(k, self._process_fieldstorage(fs[k])) for k in fs.keys()]
        )
        # FIXME: In the original collector, this returned request querystring
        # data as well as request body data.
        return form

    @staticmethod
    def _no_x00_character(value):
        """Remove x00 characters

        Note: We remove null characters because they are a hassle to deal with
        during reporting and cause problems when sending to Postgres.

        :arg value: a basestring with null characters in it

        :returns: same type basestring with null characters removed

        """
        if isinstance(value, unicode) and u'\u0000' in value:
            return u''.join(c for c in value if c != u'\u0000')
        if isinstance(value, str) and '\x00' in value:
            return ''.join(c for c in value if c != '\x00')
        return value

    def _get_raw_crash_from_form(self, req):
        """Retrieves crash/dump data and fixes it

        :arg req: the WSGI request

        :returns: (raw_crash, dumps)

        """
        dumps = MemoryDumpsMapping()
        raw_crash = {}
        checksums = {}

        for name, value in self._form_as_mapping(req).iteritems():
            name = self._no_x00_character(name)
            if isinstance(value, basestring):
                if name != "dump_checksums":
                    raw_crash[name] = self._no_x00_character(value)
            elif hasattr(value, 'file') and hasattr(value, 'value'):
                dumps[name] = value.value
                checksums[name] = self.checksum_method(value.value).hexdigest()
            elif isinstance(value, int):
                raw_crash[name] = value
            else:
                raw_crash[name] = value.value
        raw_crash['dump_checksums'] = checksums
        return raw_crash, dumps

    def on_post(self, req, resp):
        raw_crash, dumps = self._get_raw_crash_from_form(req)

        # Set the content-type now. That way we can drop out of this method
        # whenever.
        resp.content_type = 'text/plain'

        current_timestamp = utc_now()
        raw_crash['submitted_timestamp'] = current_timestamp.isoformat()
        # legacy - ought to be removed someday
        raw_crash['timestamp'] = time.time()

        if not self.accept_submitted_crash_id or 'uuid' not in raw_crash:
            crash_id = create_new_ooid(current_timestamp)
            raw_crash['uuid'] = crash_id
            logger.info('%s received', crash_id)
        else:
            crash_id = raw_crash['uuid']
            logger.info('%s received with existing crash_id:', crash_id)

        if ('legacy_processing' not in raw_crash or
                not self.accept_submitted_legacy_processing):

            raw_crash['legacy_processing'], raw_crash['throttle_rate'] = (
                self.throttler.throttle(raw_crash)
            )
        else:
            raw_crash['legacy_processing'] = int(
                raw_crash['legacy_processing']
            )

        if raw_crash['legacy_processing'] == DISCARD:
            logger.info('%s discarded', crash_id)
            resp.data = 'Discarded=1\n'
            return
        if raw_crash['legacy_processing'] == IGNORE:
            logger.info('%s ignored', crash_id)
            resp.data = 'Unsupported=1\n'
            return

        raw_crash['type_tag'] = self.dump_id_prefix.strip('-')

        self.crash_storage.save_raw_crash(
            raw_crash,
            dumps,
            crash_id
        )
        logger.info('%s accepted', crash_id)

        resp.status = falcon.HTTP_200
        resp.data = 'CrashID=%s%s\n' % (self.dump_id_prefix, crash_id)


class HealthCheckResource(object):
    def __init__(self, config):
        self.username = config('USERNAME', namespace='healthcheck')
        self.password = config('PASSWORD', namespace='healthcheck')

    def is_valid_auth(self, username, password):
        return (self.username, self.password) == (username, password)

    @require_basic_auth
    def on_get(self, req, resp):
        resp.content_type = 'application/json'

        # FIXME: This should query all the subsystems/components/whatever and
        # provide data from them. We need a registration system or something to
        # facilitate that programmatically.
        #
        # Once we know how everything is doing, we can determine the proper
        # status code. For now, 200 is fine.
        resp.status = falcon.HTTP_200
        resp.data = json.dumps({
            'health': 'v1',
        })


def get_app():
    config = ConfigManager([ConfigOSEnv()])
    app = falcon.API()
    app.add_route('/api/v1/health', HealthCheckResource(config))
    app.add_route('/submit', BreakpadSubmitterResource(config))
    return app
