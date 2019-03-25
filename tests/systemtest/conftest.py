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
from google.cloud import pubsub_v1
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
        """Return list of keys in S3 bucket."""
        self.logger.info('listing "%s" for prefix "%s"', self.bucket, prefix)
        resp = self.conn.list_objects(Bucket=self.bucket, Prefix=prefix, RequestPayer='requester')
        return [obj['Key'] for obj in resp['Contents']]


@pytest.fixture
def s3conn(config):
    """Generate and returns an S3 connection using env config."""
    return S3Connection(
        access_key=config('crashstorage_access_key', default=''),
        secret_access_key=config('crashstorage_secret_access_key', default=''),
        endpointurl=config('crashstorage_endpoint_url', default=''),
        region=config('crashstorage_region', default='us-west-2'),
        bucket=config('crashstorage_bucket_name'),
    )


class PubSubHelper:
    def __init__(self, project_id, topic_name, subscription_name):
        self.subscription = pubsub_v1.SubscriberClient()
        self.topic_path = self.subscription.topic_path(project_id, topic_name)
        self.subscription_path = self.subscription.subscription_path(project_id, subscription_name)

    def list_crashids(self):
        """Return crash ids in the Pub/Sub topic."""
        crashids = []
        while True:
            response = self.subscription.pull(
                self.subscription_path, max_messages=1, return_immediately=True
            )
            if not response.received_messages:
                break

            ack_ids = []
            for msg in response.received_messages:
                if msg.message.data != 'test':
                    crashids.append(msg.message.data)
                ack_ids.append(msg.ack_id)

            # Acknowledges the received messages so they will not be sent again.
            self.subscription.acknowledge(self.subscription_path, ack_ids)
        return crashids


@pytest.fixture
def pubsub(config):
    """Generate and returns a PubSub helper using env config."""
    return PubSubHelper(
        project_id=config('crashpublish_project_id', default=''),
        topic_name=config('crashpublish_topic_name', default=''),
        subscription_name=config('crashpublish_subscription_name', default=''),
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
