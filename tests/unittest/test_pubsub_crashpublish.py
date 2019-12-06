# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import io

from google.api_core.exceptions import NotFound
from google.cloud import pubsub_v1
import pytest

from testlib.mini_poster import multipart_encode


class PubSubHelper:
    def __init__(self):
        self._publisher = pubsub_v1.PublisherClient()
        self._subscriber = pubsub_v1.SubscriberClient()

        self._subscriptions = []
        self._topics = []

    def cleanup(self):
        """Clean up Pub/Sub things created in tests."""
        # Delete all subscriptions
        for subscription_path in self._subscriptions:
            self._subscriber.delete_subscription(subscription_path)

        # Delete all topics that exist
        for topic_path in self._topics:
            self._publisher.delete_topic(topic_path)

    def create_topic(self, project_id, topic_name):
        """Create a topic for a given project and return topic path."""
        topic_path = self._publisher.topic_path(project_id, topic_name)

        self._publisher.create_topic(topic_path)
        self._topics.append(topic_path)
        return topic_path

    def create_subscription(self, project_id, topic_name, subscription_name):
        """Create a subscription for a given topic and return subscription path."""
        topic_path = self._subscriber.topic_path(project_id, topic_name)
        subscription_path = self._subscriber.subscription_path(
            project_id, subscription_name
        )

        self._subscriber.create_subscription(subscription_path, topic_path)
        self._subscriptions.append(subscription_path)
        return subscription_path

    def get_published_crashids(self, subscription_path):
        """Get crash ids published to the subscribed topic.

        You need to create the subscription before publishing to the topic.
        Subscriptions can't see what was published before they were created.

        """
        self._subscriber.get_subscription(subscription_path)
        crashids = []
        while True:
            resp = self._subscriber.pull(
                subscription_path, max_messages=1, return_immediately=True
            )
            if not resp.received_messages:
                break

            ack_ids = []
            for msg in resp.received_messages:
                crashids.append(msg.message.data)
                ack_ids.append(msg.ack_id)
            self._subscriber.acknowledge(subscription_path, ack_ids)
        return crashids


@pytest.fixture
def pubsub():
    """Pub/Sub helper fixture."""
    pubsub = PubSubHelper()

    yield pubsub

    pubsub.cleanup()


class TestPubSubCrashPublishIntegration:
    def test_verify_topic_no_topic(self, client, pubsub):
        # Rebuild the app the test client is using with relevant
        # configuration--this will call verify_topic() which will balk because
        # the topic doesn't exist.
        with pytest.raises(NotFound):
            client.rebuild_app(
                {
                    "CRASHPUBLISH_CLASS": "antenna.ext.pubsub.crashpublish.PubSubCrashPublish",
                    "CRASHPUBLISH_PROJECT_ID": "test_socorro",
                    "CRASHPUBLISH_TOPIC_NAME": "test_socorro_standard",
                }
            )

    def test_verify_topic_with_topic(self, client, pubsub):
        PROJECT = "test_socorro"
        TOPIC = "test_socorro_standard"
        SUB = "test_subscription"

        pubsub.create_topic(PROJECT, TOPIC)
        subscription_path = pubsub.create_subscription(PROJECT, TOPIC, SUB)

        # Set up topic and subscription

        # Rebuild the app the test client is using with relevant configuration--this
        # will call verify_topic() which will work fine.
        client.rebuild_app(
            {
                "CRASHPUBLISH_CLASS": "antenna.ext.pubsub.crashpublish.PubSubCrashPublish",
                "CRASHPUBLISH_PROJECT_ID": PROJECT,
                "CRASHPUBLISH_TOPIC_NAME": TOPIC,
            }
        )

        # Assert "test" crash id was published
        crashids = pubsub.get_published_crashids(subscription_path)
        assert crashids == [b"test"]

    def test_crash_publish(self, client, pubsub):
        PROJECT = "test_socorro"
        TOPIC = "test_socorro_standard"
        SUB = "test_subscription"

        pubsub.create_topic(PROJECT, TOPIC)
        subscription_path = pubsub.create_subscription(PROJECT, TOPIC, SUB)

        data, headers = multipart_encode(
            {
                "uuid": "de1bb258-cbbf-4589-a673-34f800160918",
                "ProductName": "Fennec",
                "Version": "1.0",
                "upload_file_minidump": ("fakecrash.dump", io.BytesIO(b"abcd1234")),
            }
        )

        # Rebuild the app the test client is using with relevant configuration
        client.rebuild_app(
            {
                "CRASHPUBLISH_CLASS": "antenna.ext.pubsub.crashpublish.PubSubCrashPublish",
                "CRASHPUBLISH_PROJECT_ID": PROJECT,
                "CRASHPUBLISH_TOPIC_NAME": TOPIC,
            }
        )

        # Slurp off the "test" crash id from verification
        pubsub.get_published_crashids(subscription_path)

        result = client.simulate_post("/submit", headers=headers, body=data)
        client.join_app()

        # Verify the collector returns a 200 status code and the crash id
        # we fed it.
        assert result.status_code == 200
        assert result.content == b"CrashID=bp-de1bb258-cbbf-4589-a673-34f800160918\n"

        # Assert crash id was published
        crashids = pubsub.get_published_crashids(subscription_path)
        assert crashids == [b"de1bb258-cbbf-4589-a673-34f800160918"]
