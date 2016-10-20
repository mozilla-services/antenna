# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import cgi
from collections import OrderedDict
import hashlib
import io
import json
import logging
import os
import logging.config
import time
import zlib

from everett.manager import ConfigManager, ConfigEnvFileEnv, ConfigOSEnv, parse_class
from everett.component import ConfigOptions, RequiredConfigMixin
import falcon
from falcon.http_error import HTTPError
from gevent.pool import Pool

from antenna.datetimeutil import utc_now
from antenna.util import create_crash_id, de_null


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
                'format': '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S %z',
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


class HomePageResource:
    def __init__(self, config):
        pass

    def on_get(self, req, resp):
        resp.content_type = 'text/html'
        resp.status = falcon.HTTP_200
        resp.body = '<html><body><p>I am Antenna.</p></body></html>'


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
        self.crashstorage = self.config('crashstorage_class')(config.with_namespace('crashstorage'))

        # Gevent pool for handling incoming crash reports
        self.pipeline_pool = Pool()

    def check_health(self, state):
        state.add_statsd(self, 'queue_size', len(self.pipeline_pool))
        if hasattr(self.crashstorage, 'check_health'):
            self.crashstorage.check_health(state)

    def extract_payload(self, req):
        """Parses the HTTP POST payload

        Decompresses the payload if necessary and then walks through the
        FieldStorage converting from multipart/form-data to Python datatypes.

        Note: The FieldStorage is poorly documented (in my opinion). It has a
        list attribute that is a list of FieldStorage items--one for each
        key/val in the form. For attached files, the FieldStorage will have a
        name, value and filename and the type should be
        application/octet-stream. Thus we parse it looking for things of type
        text/plain and application/octet-stream.

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
            req.env['CONTENT_LENGTH'] = str(len(data))

            data = io.BytesIO(data)
        else:
            data = req.stream

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

            elif fs_item.type.startswith('application/octet-stream') or isinstance(fs_item.value, bytes):
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

    def on_post(self, req, resp):
        resp.content_type = 'text/plain'

        raw_crash, dumps = self.extract_payload(req)

        current_timestamp = utc_now()
        raw_crash['submitted_timestamp'] = current_timestamp.isoformat()
        # FIXME(willkg): Check the processor to see if we can remove this.
        raw_crash['timestamp'] = time.time()

        if 'uuid' not in raw_crash:
            crash_id = create_crash_id(current_timestamp)
            raw_crash['uuid'] = crash_id
            logger.info('%s received', crash_id)
        else:
            # FIXME(willkg): This means the uuid is essentially user-provided.
            # We should sanitize it before proceeding.
            crash_id = raw_crash['uuid']
            logger.info('%s received with existing crash_id', crash_id)

        # NOTE(willkg): The old collector add "legacy_processing" and
        # "throttle_rate" which come from throttling. The new collector doesn't
        # throttle, so that gets added by the processor.

        # FIXME(willkg): The processor should only throttle *new* crashes
        # and not crashes coming into the priority or reprocessing queues.

        raw_crash['type_tag'] = self.config('dump_id_prefix').strip('-')

        self.pipeline_pool.spawn(
            self.post_process,
            raw_crash=raw_crash,
            dumps=dumps,
            crash_id=crash_id
        )

        logger.info('%s accepted', crash_id)

        resp.status = falcon.HTTP_200
        resp.body = 'CrashID=%s%s\n' % (self.config('dump_id_prefix'), crash_id)

    # FIXME(willkg): Need a better name than "post_process"
    def post_process(self, raw_crash, dumps, crash_id):
        """Handles received crash and saves it"""

        # FIXME(willkg): How to deal with errors here? The save_raw_crash should
        # handle retrying, so if it bubbles up to this point, then it's an
        # unretryable unhandleable error.
        #
        # We need to mark this node as unhealthy with the reason.

        # Save the crash to crashstorage
        self.crashstorage.save_raw_crash(
            raw_crash,
            dumps,
            crash_id
        )
        logger.info('%s saved', crash_id)

    def join_pool(self):
        """Joins the pool--use only in tests!

        This is helpful for forcing everything to finish so that we can verify
        outcomes in the test suite.

        """
        self.pipeline_pool.join()


class VersionResource:
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


class LBHeartbeatResource:
    """Endpoint to let the load balancing know application health"""
    def __init__(self, config):
        self.config = config

    def on_get(self, req, resp):
        resp.status = falcon.HTTP_200


class HealthState:
    def __init__(self):
        self.errors = []
        self.statsd = {}

    def add_statsd(self, name, key, value):
        if not isinstance(name, str):
            name = name.__class__.__name__
        self.statsd['%s.%s' % (name, key)] = value

    def add_error(self, name, msg):
        # Use an OrderedDict here so we can maintain key order when converting
        # to JSON.
        d = OrderedDict([('name', name), ('msg', msg)])
        self.errors.append(d)

    def is_healthy(self):
        return len(self.errors) == 0

    def to_dict(self):
        return OrderedDict([
            ('errors', self.errors),
            ('info', self.statsd)
        ])


class HeartbeatResource:
    def __init__(self, config, app):
        self.config = config
        self.antenna_app = app

    def on_get(self, req, resp):
        state = HealthState()

        # So we're going to think of Antenna like a big object graph and
        # traverse passing along the HealthState instance. Then, after
        # traversing the object graph, we'll tally everything up and deliver
        # the news.
        for name, resource in self.antenna_app._all_resources.items():
            if hasattr(resource, 'check_health'):
                resource.check_health(state)

        # FIXME(willkg): statsd things here

        if state.is_healthy():
            resp.status = falcon.HTTP_200
        else:
            resp.status = falcon.HTTP_503
        resp.body = json.dumps(state.to_dict())


class AntennaAPI(falcon.API):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._all_resources = {}

    def unhandled_exception_handler(self, ex, req, resp, params):
        # FIXME(willkg): Falcon 1.1 makes error handling better, so we should rewrite
        # this then.

        if not isinstance(ex, HTTPError):
            # Something unhandled happened. We want to log it so we know about it and
            # then let falcon do it's thing.
            logger.exception('Unhandled exception')
        raise

    def add_route(self, name, uri_template, resource, *args, **kwargs):
        self._all_resources[name] = resource
        super().add_route(uri_template, resource, *args, **kwargs)

    def get_resource_by_name(self, name):
        return self._all_resources[name]

    def get_resources(self):
        return self._all_resources.values()


def get_app(config=None):
    """Returns AntennaAPI instance"""
    if config is None:
        config = ConfigManager([
            # Pull configuration from env file specified as ANTENNA_ENV
            ConfigEnvFileEnv([os.environ.get('ANTENNA_ENV')]),
            # Pull configuration from environment variables
            ConfigOSEnv()
        ])

    setup_logging(config)
    app_config = AppConfig(config)

    app = AntennaAPI(config)
    app.add_error_handler(Exception, handler=app.unhandled_exception_handler)

    app.add_route('homepage', '/', HomePageResource(config))
    app.add_route('breakpad', '/submit', BreakpadSubmitterResource(config))
    app.add_route('version', '/__version__', VersionResource(config, basedir=app_config('basedir')))
    app.add_route('heartbeat', '/__heartbeat__', HeartbeatResource(config, app))
    app.add_route('lbheartbeat', '/__lbheartbeat__', LBHeartbeatResource(config))
    return app
