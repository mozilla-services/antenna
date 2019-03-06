# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

from everett.component import ConfigOptions
from google.cloud import pubsub_v1

from antenna.ext.crashpublish_base import CrashPublishBase
from antenna.heartbeat import register_for_verification


logger = logging.getLogger(__name__)

# This is the maximum time in seconds that a batch will sit around for before
# getting published. Since .pubish_crash() is synchronous (it blocks on the
# result), I think we want this short-ish. But it's nice to batch publishing.
#
# NOTE(willkg): Maybe think about making this configurable so we can find a
# more optimal value? Maybe calculate it based on concurrant crashmovers value?
BATCH_MAX_LATENCY = 0.5


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

    You need to set the environment variable ``GOOGLE_APPLICATION_CREDENTIALS``
    to the absolute path of the JSON creds file for the service account.

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

        # Batches crash_ids for at most BATCH_MAX_LATENCY seconds
        self.batch_settings = pubsub_v1.types.BatchSettings(max_latency=BATCH_MAX_LATENCY)
        self.publisher = pubsub_v1.PublisherClient(self.batch_settings)
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)

        register_for_verification(self.verify_topic)

    def verify_topic(self):
        """Verify topic exists and can be viewed."""
        # Publish a fake crash id
        future = self.publisher.publish(self.topic_path, data=b'test')

        # This will block until the crash has been published; if it publishes
        # we're good to go
        future.result()

    def publish_crash(self, crash_id):
        """Publish a crash id to a Pub/Sub topic."""
        data = crash_id.encode('utf-8')
        future = self.publisher.publish(self.topic_path, data=data)

        # This forces publishing to be synchronous so if there are problems,
        # this will raise an exception and that'll get handled by the retry
        # logic.
        future.result()
