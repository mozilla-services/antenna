# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import io
import os

import boto3
from botocore.exceptions import ClientError
import pytest

from testlib.mini_poster import multipart_encode


class SQSHelper:
    def __init__(self):
        self.client = self._build_client()
        self._queues = []

    def cleanup(self):
        """Clean up SQS queues creating in tests."""
        for queue_name in self._queues:
            queue_url = self.client.get_queue_url(QueueName=queue_name)["QueueUrl"]
            self.client.delete_queue(QueueUrl=queue_url)

    def _build_client(self):
        """Build a client."""
        session = boto3.session.Session(
            aws_access_key_id=os.environ.get("CRASHMOVER_CRASHPUBLISH_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get(
                "CRASHMOVER_CRASHPUBLISH_SECRET_ACCESS_KEY"
            ),
        )
        client = session.client(
            service_name="sqs",
            region_name=os.environ.get("CRASHMOVER_CRASHPUBLISH_REGION"),
            endpoint_url=os.environ.get("CRASHMOVER_CRASHPUBLISH_ENDPOINT_URL"),
        )
        return client

    def create_queue(self, queue_name):
        """Create a queue."""
        self.client.create_queue(QueueName=queue_name)
        self._queues.append(queue_name)

    def get_published_crashids(self, queue_name):
        """Get crash ids published to the queue."""
        queue_url = self.client.get_queue_url(QueueName=queue_name)["QueueUrl"]
        all_crashids = []
        while True:
            resp = self.client.receive_message(
                QueueUrl=queue_url,
                WaitTimeSeconds=0,
                VisibilityTimeout=1,
            )
            msgs = resp.get("Messages", [])
            if not msgs:
                return all_crashids
            all_crashids.extend([msg["Body"] for msg in msgs])


@pytest.fixture
def sqs():
    """AWS SQS helper fixture."""
    sqs = SQSHelper()

    yield sqs

    sqs.cleanup()


class TestSQSCrashPublishIntegration:
    def test_verify_queue_no_queue(self, client, sqs):
        # Rebuild the app the test client is using with relevant configuration--this
        # will call verify_queue() which will balk because the queue doesn't exist.
        with pytest.raises(ClientError):
            client.rebuild_app(
                {
                    "CRASHMOVER_CRASHPUBLISH_CLASS": "antenna.ext.sqs.crashpublish.SQSCrashPublish",
                    "CRASHMOVER_CRASHPUBLISH_QUEUE_NAME": "test_socorro",
                }
            )

    def test_verify_topic_with_queue(self, client, sqs):
        queue_name = "test_socorro"
        sqs.create_queue(queue_name)

        # Rebuild the app the test client is using with relevant configuration--this
        # will call verify_topic() which will work fine.
        client.rebuild_app(
            {
                "CRASHMOVER_CRASHPUBLISH_CLASS": "antenna.ext.sqs.crashpublish.SQSCrashPublish",
                "CRASHMOVER_CRASHPUBLISH_QUEUE_NAME": "test_socorro",
            }
        )

        # Assert "test" crash id was published
        crashids = sqs.get_published_crashids(queue_name)
        assert crashids == ["test"]

    def test_crash_publish(self, client, sqs):
        queue_name = "test_socorro"
        sqs.create_queue(queue_name)

        data, headers = multipart_encode(
            {
                "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
                "ProductName": "Firefox",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        # Rebuild the app the test client is using with relevant configuration
        client.rebuild_app(
            {
                "CRASHMOVER_CRASHPUBLISH_CLASS": "antenna.ext.sqs.crashpublish.SQSCrashPublish",
                "CRASHMOVER_CRASHPUBLISH_QUEUE_NAME": "test_socorro",
            }
        )

        # Slurp off the "test" crash id from verification
        sqs.get_published_crashids(queue_name)

        result = client.simulate_post("/submit", headers=headers, body=data)

        # Verify the collector returns a 200 status code and the crash id
        # we fed it.
        assert result.status_code == 200
        assert result.content == b"CrashID=bp-de1bb258-cbbf-4589-a673-34f800160918\n"

        # Assert crash id was published
        crashids = sqs.get_published_crashids(queue_name)
        assert crashids == ["de1bb258-cbbf-4589-a673-34f800160918"]
