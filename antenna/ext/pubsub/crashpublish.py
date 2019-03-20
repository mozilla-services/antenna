# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os

from everett.component import ConfigOptions
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.publisher import futures
from google.cloud.pubsub_v1.types import PubsubMessage

from antenna.ext.crashpublish_base import CrashPublishBase
from antenna.heartbeat import register_for_verification


logger = logging.getLogger(__name__)


class SynchronousBatch:
    """Synchronous batch class.

    Instead of batching published messages and then spinning off a thread to
    send them as a batch at some point later, this sends messages as they are
    published. In this way, any exceptions thrown while publishing bubble up to
    the right place in Antenna and get handled correctly.

    """

    def __init__(self, client, topic, settings, autocommit=True):
        self._client = client
        self._topic = topic
        self._settings = settings
        self._autocommit = autocommit

    def publish(self, message):
        """Publish message.

        This publishes messages immediately--it does no batching and requires
        no threads.

        """
        if not isinstance(message, PubsubMessage):
            message = PubsubMessage(**message)

        # Publish and return result wrapped in future
        future = futures.Future()
        resp = self._client.api.publish(self._topic, [message], timeout=5)
        future.set_result(resp.message_ids[0])
        return future


class PubSubCrashPublish(CrashPublishBase):
    """Publisher to Pub/Sub.

    Required GCP things
    ===================

    To use this, you need to create:

    1. Google Compute project
    2. topic in that project
    3. service account with publisher permissions to the topic
    4. JSON creds file for the service account placed in
    5. subscription for that topic so you can consume queued items

    If something in the above isn't created, then Antenna may not start.


    Verification
    ============

    This component verifies that it can publish to the topic by publishing a
    fake crash id of ``test``. Downstream consumer should throw this out.


    Local emulaior
    ==============

    If you set the environment variable ``PUBSUB_EMULATOR_HOST=host:port``,
    then this will connect to a local Pub/Sub emulator.

    """

    required_config = ConfigOptions()
    required_config.add_option(
        'service_account_file',
        default='',
        doc='The absolute path to the Google Cloud service account credentials file.'
    )
    required_config.add_option(
        'project_id',
        doc='Google Cloud project id.'
    )
    required_config.add_option(
        'topic_name',
        doc='The Pub/Sub topic name to publish to.'
    )

    def __init__(self, config):
        super().__init__(config)

        self.project_id = self.config('project_id')
        self.topic_name = self.config('topic_name')

        if os.environ.get('PUBSUB_EMULATOR_HOST', ''):
            self.publisher = pubsub_v1.PublisherClient()
        else:
            self.publisher = pubsub_v1.PublisherClient.from_service_account_file(
                self.config('service_account_file')
            )
        self.publisher._batch_class = SynchronousBatch
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)

        register_for_verification(self.verify_topic)

    def verify_topic(self):
        """Verify topic can be published to by publishing fake crash id."""
        future = self.publisher.publish(self.topic_path, data=b'test')
        future.result()

    def check_health(self, state):
        """Check Pub/Sub connection health."""
        try:
            self.publisher.get_topic(self.topic_path)
        except Exception as exc:
            state.add_error('PubSubCrashPublish', repr(exc))

    def publish_crash(self, crash_report):
        """Publish a crash id to a Pub/Sub topic."""
        crash_id = crash_report.crash_id
        data = crash_id.encode('utf-8')
        future = self.publisher.publish(self.topic_path, data=data)
        future.result()
