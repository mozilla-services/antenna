# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging

from everett.manager import Option
from google.cloud.pubsub_v1 import PublisherClient
from google.cloud.pubsub_v1.types import BatchSettings

from antenna.ext.crashpublish_base import CrashPublishBase
from antenna.app import register_for_verification


logger = logging.getLogger(__name__)


class PubSubCrashPublish(CrashPublishBase):
    """Publisher to Pub/Sub.

    **Required GCP things**

    To use this, you need to create:

    1. Google Compute project
    2. topic in that project
    3. service account with publisher permissions to the topic
    4. JSON creds file for the service account placed in
    5. subscription for that topic so you can consume queued items

    If something in the above isn't created, then Antenna may not start.


    **Verification**

    This component verifies that it can publish to the topic by publishing a
    fake crash id of ``test``. Downstream consumer should throw this out.


    **Local emulaior**

    If you set the environment variable ``PUBSUB_EMULATOR_HOST=host:port``,
    then this will connect to a local Pub/Sub emulator.

    """

    class Config:
        service_account_file = Option(
            default="",
            doc="The absolute path to the Google Cloud service account credentials file.",
        )
        project_id = Option(doc="Google Cloud project id.")
        topic_name = Option(doc="The Pub/Sub topic name to publish to.")

    def __init__(self, config):
        super().__init__(config)

        self.project_id = self.config("project_id")
        self.topic_name = self.config("topic_name")

        # publish messages immediately without queuing.
        batch_settings = BatchSettings(max_messages=1)
        service_account_file = self.config("service_account_file")
        if service_account_file:
            self.publisher = PublisherClient.from_service_account_file(
                service_account_file, batch_settings
            )
        else:
            self.publisher = PublisherClient(batch_settings)

        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)

        register_for_verification(self.verify_topic)

    def _publish(self, data: bytes):
        """Publish message directly without queuing."""
        future = self.publisher.publish(self.topic_path, data)
        future.result()

    def verify_topic(self):
        """Verify topic can be published to by publishing fake crash id."""
        future = self.publisher.publish(self.topic_path, b"test")
        future.result()

    def check_health(self, state):
        """Check Pub/Sub connection health."""
        try:
            self.publisher.get_topic(topic=self.topic_path)
        except Exception as exc:
            state.add_error("PubSubCrashPublish", repr(exc))

    def publish_crash(self, crash_report):
        """Publish a crash id to a Pub/Sub topic."""
        data = crash_report.crash_id.encode("utf-8")
        future = self.publisher.publish(self.topic_path, data)
        future.result()
