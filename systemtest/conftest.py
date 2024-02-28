# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
from pathlib import Path
import sys
import os

import boto3
from botocore.client import Config
from everett.manager import ConfigManager, ConfigOSEnv
from google.cloud import pubsub_v1
import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage


# Add repository root so we can import testlib
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Set up logging to log at INFO level; this is quelled by pytest except when
# there are errors
logging.basicConfig(level=logging.INFO)


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
    """Return whether or not we can verify the file was saved (need access to S3/GCS)"""
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


class GcsHelper:
    def __init__(self, bucket):
        self.bucket = bucket

        self.logger = logging.getLogger(__name__ + ".gcs_helper")

        if os.environ.get("STORAGE_EMULATOR_HOST"):
            self.client = storage.Client(
                credentials=AnonymousCredentials(), project="test"
            )
        else:
            self.client = storage.Client()

    def get_config(self):
        return {
            "helper": "gcs",
            "bucket": self.bucket,
        }

    def list_objects(self, prefix):
        """Return list of keys in GCS bucket."""
        self.logger.info('listing "%s" for prefix "%s"', self.bucket, prefix)
        bucket = self.client.get_bucket(self.bucket)
        return [blob.name for blob in list(bucket.list_blobs(prefix=prefix))]


class S3Helper:
    def __init__(self, access_key, secret_access_key, endpoint_url, region, bucket):
        self.access_key = access_key
        self.secret_access_key = secret_access_key
        self.endpoint_url = endpoint_url
        self.region = region
        self.bucket = bucket

        self.logger = logging.getLogger(__name__ + ".s3_helper")
        self.conn = self.connect()

    def get_config(self):
        return {
            "helper": "s3",
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


@pytest.fixture(params=["gcs", "s3"])
def storage_helper(config, request):
    """Generate and returns an S3 or GCS helper using env config."""
    configured_backend = "s3"
    if (
        config("crashmover_crashstorage_class")
        == "antenna.ext.gcs.crashstorage.GcsCrashStorage"
    ):
        configured_backend = "gcs"

    if configured_backend != request.param:
        pytest.skip(f"test requires {request.param}")

    if configured_backend == "gcs":
        return GcsHelper(
            bucket=config("crashmover_crashstorage_bucket_name"),
        )
    return S3Helper(
        access_key=config("crashmover_crashstorage_access_key", default=""),
        secret_access_key=config(
            "crashmover_crashstorage_secret_access_key", default=""
        ),
        endpoint_url=config("crashmover_crashstorage_endpoint_url", default=""),
        region=config("crashmover_crashstorage_region", default="us-west-2"),
        bucket=config("crashmover_crashstorage_bucket_name"),
    )


class PubSubHelper:
    def __init__(self, project_id, topic_name, subscription_name):
        self._publisher = pubsub_v1.PublisherClient(
            pubsub_v1.types.BatchSettings(max_messages=1)
        )
        self._subscriber = pubsub_v1.SubscriberClient()

        self.topic_path = self._subscriber.topic_path(project_id, topic_name)
        self.subscription_path = self._subscriber.subscription_path(
            project_id, subscription_name
        )

    def list_crashids(self):
        """Get crash ids published to the subscribed topic.

        You need to create the subscription before publishing to the topic.
        Subscriptions can't see what was published before they were created.

        """
        # if there are no messages then pull will block for a long time, so
        # publish a message to ensure that failing tests don't take forever
        self._publisher.publish(topic=self.topic_path, data=b"ignore", timeout=5)
        crashids = []

        resp = self._subscriber.pull(
            subscription=self.subscription_path, max_messages=100
        )
        ack_ids = []
        for msg in resp.received_messages:
            if msg.message.data != b"ignore":
                crashids.append(msg.message.data.decode("utf-8"))
            ack_ids.append(msg.ack_id)
        if ack_ids:
            self._subscriber.acknowledge(
                subscription=self.subscription_path, ack_ids=ack_ids
            )
        return crashids


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
                QueueUrl=queue_url,
                WaitTimeSeconds=0,
                VisibilityTimeout=2,
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


@pytest.fixture(params=["pubsub", "sqs"])
def queue_helper(config, request):
    """Generate and returns a PubSub or SQS helper using env config."""
    configured_backend = "sqs"
    if (
        config("crashmover_crashpublish_class")
        == "antenna.ext.pubsub.crashpublish.PubSubCrashPublish"
    ):
        configured_backend = "pubsub"

    if configured_backend != request.param:
        pytest.skip(f"test requires {request.param}")

    if configured_backend == "pubsub":
        return PubSubHelper(
            project_id=config("crashmover_crashpublish_project_id", default=""),
            topic_name=config("crashmover_crashpublish_topic_name", default=""),
            subscription_name=config(
                "crashmover_crashpublish_subscription_name", default=""
            ),
        )
    return SQSHelper(
        access_key=config("crashmover_crashpublish_access_key", default=""),
        secret_access_key=config(
            "crashmover_crashpublish_secret_access_key", default=""
        ),
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


class CrashVerifier:
    def raw_crash_key(self, crash_id):
        return "v1/raw_crash/{date}/{crashid}".format(
            date="20" + crash_id[-6:], crashid=crash_id
        )

    def dump_names_key(self, crash_id):
        return f"v1/dump_names/{crash_id}"

    def dump_key(self, crash_id, name):
        if name in (None, "", "upload_file_minidump"):
            name = "dump"

        return f"v1/{name}/{crash_id}"

    def verify_stored_data(self, crash_id, raw_crash, dumps, storage_helper):
        # Verify the raw crash file made it
        key = self.raw_crash_key(crash_id)
        assert key in storage_helper.list_objects(prefix=key)

        # Verify the dump_names file made it
        key = self.dump_names_key(crash_id)
        assert key in storage_helper.list_objects(prefix=key)

        # Verify the dumps made it
        for name in dumps.keys():
            key = self.dump_key(crash_id, name)
            assert key in storage_helper.list_objects(prefix=key)

    def verify_published_data(self, crash_id, queue_helper):
        # Verify crash id was published--this might pick up a bunch of stuff,
        # so we just verify it's one of the things we picked up
        assert crash_id in queue_helper.list_crashids()


@pytest.fixture
def crash_verifier():
    return CrashVerifier()
