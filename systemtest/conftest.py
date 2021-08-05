# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
from pathlib import Path
import sys

import boto3
from botocore.client import Config
from everett.manager import ConfigManager, ConfigOSEnv
import pytest


# Add repository root so we can import testlib
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Set up logging to log at DEBUG level; this is quelled by pytest except when
# there are errors
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def config():
    cfg = ConfigManager([ConfigOSEnv()])
    return cfg


@pytest.fixture
def nginx(config):
    """Returns whether NGINX_TESTS=1"""
    return config("nginx_tests", default="0") == "1"


@pytest.fixture
def postcheck(config):
    """Return whether or not we can verify the file was saved (need access to S3)"""
    return config("post_check", default="0") == "1"


@pytest.fixture
def baseurl(config):
    """Generates base url based on os.environ"""
    return config("host", default="http://web:8000/").rstrip("/") + "/"


@pytest.fixture
def posturl(config):
    """Generates configuration based on os.environ"""
    # Endpoint url to connect to
    return config("host", default="http://web:8000/").rstrip("/") + "/submit"


class S3Connection:
    def __init__(self, access_key, secret_access_key, endpoint_url, region, bucket):
        self.access_key = access_key
        self.secret_access_key = secret_access_key
        self.endpoint_url = endpoint_url
        self.region = region
        self.bucket = bucket

        self.logger = logging.getLogger(__name__ + ".s3conn")
        self.conn = self.connect()

    def get_config(self):
        return {
            "endpoint_url": self.endpoint_url,
            "region": self.region,
            "bucket": self.bucket,
        }

    def connect(self):
        session_kwargs = {}
        if self.access_key and self.secret_access_key:
            session_kwargs["aws_access_key_id"] = self.access_key
            session_kwargs["aws_secret_access_key"] = self.secret_access_key

        session = boto3.session.Session(**session_kwargs)

        client_kwargs = {
            "service_name": "s3",
            "region_name": self.region,
            "config": Config(s3={"addression_style": "path"}),
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        client = session.client(**client_kwargs)
        return client

    def list_objects(self, prefix):
        """Return list of keys in S3 bucket."""
        self.logger.info('listing "%s" for prefix "%s"', self.bucket, prefix)
        resp = self.conn.list_objects(
            Bucket=self.bucket, Prefix=prefix, RequestPayer="requester"
        )
        return [obj["Key"] for obj in resp["Contents"]]


@pytest.fixture
def s3conn(config):
    """Generate and returns an S3 connection using env config."""
    return S3Connection(
        access_key=config("crashmover_crashstorage_access_key", default=""),
        secret_access_key=config("crashmover_crashstorage_secret_access_key", default=""),
        endpoint_url=config("crashmover_crashstorage_endpoint_url", default=""),
        region=config("crashmover_crashstorage_region", default="us-west-2"),
        bucket=config("crashmover_crashstorage_bucket_name"),
    )


class SQSHelper:
    def __init__(self, access_key, secret_access_key, endpoint_url, region, queue_name):
        self.access_key = access_key
        self.secret_access_key = secret_access_key
        self.endpoint_url = endpoint_url
        self.region = region
        self.queue_name = queue_name
        self.client = self.connect()

    def connect(self):
        session_kwargs = {}
        if self.access_key and self.secret_access_key:
            session_kwargs["aws_access_key_id"] = self.access_key
            session_kwargs["aws_secret_access_key"] = self.secret_access_key

        session = boto3.session.Session(**session_kwargs)

        client_kwargs = {
            "service_name": "sqs",
            "region_name": self.region,
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        client = session.client(**client_kwargs)
        return client

    def list_crashids(self):
        """Return crash ids in the SQS queue."""
        queue_url = self.client.get_queue_url(QueueName=self.queue_name)["QueueUrl"]

        crashids = []
        while True:
            resp = self.client.receive_message(
                QueueUrl=queue_url, WaitTimeSeconds=0, VisibilityTimeout=2,
            )
            msgs = resp.get("Messages", [])
            if not msgs:
                break

            for msg in msgs:
                data = msg["Body"]
                handle = msg["ReceiptHandle"]
                if data != "test":
                    crashids.append(data)

                self.client.delete_message(QueueUrl=queue_url, ReceiptHandle=handle)

        return crashids


@pytest.fixture
def sqshelper(config):
    """Generate and returns a PubSub helper using env config."""
    return SQSHelper(
        access_key=config("crashmover_crashpublish_access_key", default=""),
        secret_access_key=config("crashmover_crashpublish_secret_access_key", default=""),
        endpoint_url=config("crashmover_crashpublish_endpoint_url", default=""),
        region=config("crashmover_crashpublish_region", default=""),
        queue_name=config("crashmover_crashpublish_queue_name", default=""),
    )


class CrashGenerator:
    def generate(self, metadata=None, dumps=None):
        """Returns raw_crash, dumps"""
        # FIXME(willkg): Flesh this out to be more crash-y.
        raw_crash = {"ProductName": "Firefox", "Version": "1"}
        if dumps is None:
            dumps = {"upload_file_minidump": b"abcd1234"}

        if metadata is not None:
            raw_crash.update(metadata)

        return raw_crash, dumps


@pytest.fixture
def crash_generator():
    return CrashGenerator()
