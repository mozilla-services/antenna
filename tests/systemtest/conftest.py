# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os
from pathlib import Path
import sys

import boto3
from botocore.client import Config
from everett.manager import ConfigManager, ConfigEnvFileEnv, ConfigOSEnv
import pytest


# Add repository root so we can import testlib
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Set up logging to log at DEBUG level; this is quelled by pytest except when
# there are errors
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def config():
    cfg = ConfigManager([
        ConfigEnvFileEnv([os.environ.get('ANTENNA_ENV')]),
        ConfigOSEnv()
    ])
    return cfg


@pytest.fixture
def posturl(config):
    """Generates configuration based on os.environ"""
    # Endpoint url to connect to
    return config(
        'posturl',
        default='http://localhost:8000/submit'
    )


class S3Connection:
    def __init__(self, access_key, secret_access_key, endpointurl, region, bucket):
        self.access_key = access_key
        self.secret_access_key = secret_access_key
        self.endpointurl = endpointurl
        self.region = region
        self.bucket = bucket

        self.logger = logging.getLogger(__name__ + '.s3conn')
        self.conn = self.connect()

    def get_config(self):
        return {
            'endpointurl': self.endpointurl,
            'region': self.region,
            'bucket': self.bucket
        }

    def connect(self):
        session_kwargs = {}
        if self.access_key and self.secret_access_key:
            session_kwargs['aws_access_key_id'] = self.access_key
            session_kwargs['aws_secret_access_key'] = self.secret_access_key

        session = boto3.session.Session(**session_kwargs)

        client_kwargs = {
            'service_name': 's3',
            'region_name': self.region,
            'config': Config(s3={'addression_style': 'path'})
        }
        if self.endpointurl:
            client_kwargs['endpoint_url'] = self.endpointurl

        client = session.client(**client_kwargs)
        return client

    def list_objects(self, prefix):
        """Returns list of keys in the bucket"""
        self.logger.info('listing "%s" for prefix "%s"', self.bucket, prefix)
        # resp = self.conn.list_objects(Bucket=self.bucket, Prefix=prefix, RequestPayer='requester')
        resp = self.conn.list_objects(Bucket=self.bucket)
        print(type(resp))
        print(resp)
        return [obj['Key'] for obj in resp['Contents']]


@pytest.fixture
def s3conn(config):
    """Generates and returns an S3 connection"""
    # NOTE(willkg): These env keys match what Antenna uses so we can have one
    # .env file that works for Antenna and the system configuration.
    return S3Connection(
        # The s3 access key.
        access_key=config('crashstorage_access_key', default=''),
        # The s3 secret access key.
        secret_access_key=config('crashstorage_secret_access_key', default=''),
        # The s3 endpoint url to use.
        endpointurl=config('crashstorage_endpoint_url', default=''),
        # The s3 region to use.
        region=config('crashstorage_region', default='us-west-2'),
        # The s3 bucket to use.
        bucket=config('crashstorage_bucket_name'),
    )


class CrashGenerator:
    def generate(self, metadata=None, dumps=None):
        """Returns raw_crash, dumps"""
        # FIXME(willkg): Flesh this out to be more crash-y.
        raw_crash = {
            'ProductName': 'Firefox',
            'Version': '1',
        }
        if dumps is None:
            dumps = {
                'upload_file_minidump': b'abcd1234'
            }

        if metadata is not None:
            raw_crash.update(metadata)

        return raw_crash, dumps


@pytest.fixture
def crash_generator():
    return CrashGenerator()
