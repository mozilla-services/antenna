# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import cgi
import hashlib
import io
import logging
import os
import logging.config
import time
import zlib

from everett.manager import ConfigManager, ConfigOSEnv, parse_class
from everett.component import ConfigOptions, RequiredConfigMixin
import falcon

from antenna.lib.datetimeutil import utc_now
from antenna.lib.ooid import create_new_ooid
from antenna.util import de_null


logger = logging.getLogger(__name__)


_logging_initialized = False


class AppConfig(RequiredConfigMixin):
    """Application-level config

    To pull out a config item, you can do this::

        config = ConfigManager([ConfigOSEnv()])
        app_config = AppConfig(config)

        debug = app_config('debug')


    To create a component with configuration, you can do this::

        class SomeComponent(RequiredConfigMixin):
            required_config = ConfigOptions()

            def __init__(self, config):
                self.config = config.with_options(self)

        some_component = SomeComponent(app_config.config)


    To pass application-level configuration to components, you should do it
    through arguments like this::

        class SomeComponent(RequiredConfigMixin):
            required_config = ConfigOptions()

            def __init__(self, config, debug):
                self.config = config.with_options(self)
                self.debug = debug

        some_component = SomeComponent(app_config.config_manager, debug)

    """
    required_config = ConfigOptions()
    required_config.add_option(
        'basedir',
        default=os.path.abspath(os.path.dirname(os.path.dirname(__file__))),
        doc='The root directory for this application to find and store things.'
    )

    def __init__(self, config):
        self.config_manager = config
        self.config = config.with_options(self)

    def __call__(self, key):
        return self.config(key)


def setup_logging(config):
    """Initializes Python logging configuration

    NOTE(willkg): This causes some problems since it'll get initialized using
    the first configuration it was given. Pretty sure that'll only happen when
    running tests and we're not testing logging in tests. If that ever changes,
    we'll need to revisit this.

    """
    global _logging_initialized
    if _logging_initialized:
        return

    dc = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'development': {
                'format': '%(levelname)s %(asctime)s %(name)s %(message)s',
            },
        },
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'development',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
        'loggers': {
            'antenna': {
                'propagate': False,
                'handlers': ['console'],
                'level': 'DEBUG',
            },
        },
    }
    logging.config.dictConfig(dc)
    _logging_initialized = True


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
        default='antenna.external.crashstorage_base.NoOpCrashStorage',
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

           This is a regular form key/val pair. The value is a string.

           Example:

           * FieldStorage('ProductName', None, 'Test')
           * FieldStorage('Version', None, '1')

        2. It's a FieldStorage with a name, filename and value.

           This is a file. The value is a bytes. We ignore the filename and only
           capture the name and value.

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

        # Convert to FieldStorage and then to dict.
        fs = cgi.FieldStorage(fp=data, environ=req.env, keep_blank_values=1)
        payload = self.process_fieldstorage(fs)

        # NOTE(willkg): In the original collector, this returned request
        # querystring data as well as request body data, but we're not doing
        # that because the query string just duplicates data in the payload.

        raw_crash = {}
        dumps = {}

        for key, val in payload.items():
            if key == 'dump_checksums':
                # We don't want to pick up the dump_checksums from a raw
                # crash that was re-submitted.
                continue

            elif isinstance(val, str):
                raw_crash[key] = de_null(val)

            elif isinstance(val, bytes):
                # This is a dump, so we get a checksum and save the bits in the
                # relevant places.

                # FIXME(willkg): The dump name is essentially user-provided. We should
                # sanitize it before proceeding.
                dumps[key] = val
                checksum = hashlib.md5(val).hexdigest()
                raw_crash.setdefault('dump_checksums', {})[key] = checksum

            else:
                # This should never happen. We don't want to raise an exception
                # because that would disrupt crash collection, so we log it.
                logger.error(
                    'ERROR: Saw a value in a crash report that was not a str or bytes. %r %r',
                    key, val
                )

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
            # FIXME(willkg): This means the uuid is essentially user-provided.
            # We should sanitize it before proceeding.
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


class HealthVersionResource:
    """Implements the ``/__version__`` endpoint"""
    def __init__(self, config, basedir):
        self.config = config
        self.basedir = basedir

    def on_get(self, req, resp):
        try:
            path = os.path.join(self.basedir, 'version.json')
            with open(path, 'r') as fp:
                commit_info = fp.read().strip()
        except (IOError, OSError):
            # FIXME(willkg): Log the error
            commit_info = '{}'

        resp.content_type = 'application/json; charset=utf-8'
        resp.status = falcon.HTTP_200
        resp.body = commit_info


def get_app(config=None):
    """Returns AntennaAPI instance"""
    if config is None:
        config = ConfigManager([
            # Pull configuration from environment variables
            ConfigOSEnv()
        ])

    setup_logging(config)
    app_config = AppConfig(config)

    app = falcon.API()
    app.add_route('/__version__', HealthVersionResource(config, basedir=app_config('basedir')))
    app.add_route('/submit', BreakpadSubmitterResource(config))
    return app
