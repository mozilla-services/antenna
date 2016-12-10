import json
import logging
import os
from pathlib import Path
import sys

import boto3
from botocore.client import Config
from everett.manager import ConfigManager, ConfigEnvFileEnv, ConfigOSEnv
import pytest

# Add repository root so we can import testlib.
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


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

    # FIXME(willkg): Better name
    def list_buckets(self):
        return self.conn.list_buckets()

    # FIXME(willkg): Better name
    def head_bucket(self):
        return self.conn.head_bucket(Bucket=self.bucket)

    # FIXME(willkg): Better name
    def list_objects(self):
        for key in self.conn.list_objects(Bucket=self.bucket):
            print(key)

    def get_object(self, key, is_json=False):
        self.logger.info('fetching "%s" "%s"', self.bucket, key)
        obj = self.conn.get_object(
            Bucket=self.bucket,
            Key=key
        )
        data = obj['Body'].read()
        if is_json:
            data = json.loads(str(data, encoding='utf-8'))
        return data


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
