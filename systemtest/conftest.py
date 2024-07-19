# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
from pathlib import Path
import sys
import os

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
    """Return whether or not we can verify the file was saved (need access to storage)"""
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

    def dump_key(self, crash_id, name):
        if name in (None, "", "upload_file_minidump"):
            name = "dump"

        return f"v1/{name}/{crash_id}"

    def list_objects(self, prefix):
        """Return list of keys in GCS bucket."""
        self.logger.info('listing "%s" for prefix "%s"', self.bucket, prefix)
        bucket = self.client.get_bucket(self.bucket)
        return [blob.name for blob in list(bucket.list_blobs(prefix=prefix))]


@pytest.fixture
def storage_helper(config):
    """Generate and return a storage helper using env config."""
    return GcsHelper(
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


@pytest.fixture
def queue_helper(config):
    """Generate and return a queue helper using env config."""
    return PubSubHelper(
        project_id=config("crashmover_crashpublish_project_id", default=""),
        topic_name=config("crashmover_crashpublish_topic_name", default=""),
        subscription_name=config(
            "crashmover_crashpublish_subscription_name", default=""
        ),
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

    def verify_stored_data(self, crash_id, raw_crash, dumps, storage_helper):
        # Verify the raw crash file made it
        key = self.raw_crash_key(crash_id)
        assert key in storage_helper.list_objects(prefix=key)

        # Verify the dump_names file made it
        key = self.dump_names_key(crash_id)
        assert key in storage_helper.list_objects(prefix=key)

        # Verify the dumps made it
        for name in dumps.keys():
            key = storage_helper.dump_key(crash_id, name)
            assert key in storage_helper.list_objects(prefix=key)

    def verify_published_data(self, crash_id, queue_helper):
        # Verify crash id was published--this might pick up a bunch of stuff,
        # so we just verify it's one of the things we picked up
        assert crash_id in queue_helper.list_crashids()


@pytest.fixture
def crash_verifier():
    return CrashVerifier()
