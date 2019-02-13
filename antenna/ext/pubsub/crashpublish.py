# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

from everett.component import ConfigOptions
from google.cloud import pubsub_v1

from antenna.ext.crashpublish_base import CrashPublishBase
from antenna.heartbeat import register_for_verification


logger = logging.getLogger(__name__)


class PubSubCrashPublish(CrashPublishBase):
    """Publisher to Pub/Sub.

    This does **not** create a topic if one does not exist. Instead, it'll
    throw errors when it tries to publish to a topic that does not exist.
    Whoever sets up infrastructure is in charge of creating the topic.

    This will retry publishing several times, then give up. If it gives up, the
    crashpublisher will put the crash id back in the queue to retry again
    later.

    This creates a ``PublisherClient`` which will connect to a local Pub/Sub
    emulator if ``PUBSUB_EMULATOR_HOST=host:port`` is defined in the
    environment. Otherwise, it'll connect to Google Cloud Pub/Sub.

    """

    required_config = ConfigOptions()
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

        # Batches crash_ids for up 1024 bytes or a second
        self.batch_settings = pubsub_v1.types.BatchSettings(
            max_bytes=1024,
            max_latency=1,
        )
        self.publisher = pubsub_v1.PublisherClient(self.batch_settings)
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)

        register_for_verification(self.verify_topic)

    def verify_topic(self):
        """Verify topic exists and can be viewed.

        NOTE(willkg): This requires View permissions and doesn't actually
        guarantee we can write to the topic. To do that, we'd change what's in
        the queue and that's not great.

        """
        self.publisher.get_topic(self.topic_path)

    # FIXME(willkg): In what circumstances should this retry? Also, how
    # does failure work with batching?
    def publish_crash(self, crash_id):
        """Publish a crash id to a Pub/Sub topic."""
        data = crash_id.encode('utf-8')
        self.publisher.publish(self.topic_path, data=data)
