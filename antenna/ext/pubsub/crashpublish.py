# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
import os

from everett.manager import Option
from google.cloud.pubsub_v1 import PublisherClient
from google.cloud.pubsub_v1.types import BatchSettings, PublisherOptions

from antenna.ext.crashpublish_base import CrashPublishBase
from antenna.app import register_for_verification


logger = logging.getLogger(__name__)


class PubSubCrashPublish(CrashPublishBase):
    """Publisher to Pub/Sub.

    **Required GCP things**

    To use this, you need to create:

    1. Google Compute project
    2. topic in that project
    3. subscription for that topic so you can consume queued items

    If something in the above isn't created, then Antenna may not start.


    **Verification**

    This component verifies that it can publish to the topic by publishing a
    fake crash id of ``test``. Downstream consumer should throw this out.


    **Authentication**

    The google cloud sdk will automatically detect credentials as described in
    https://googleapis.dev/python/google-api-core/latest/auth.html:

    - If you're running in a Google Virtual Machine Environment (Compute Engine, App
      Engine, Cloud Run, Cloud Functions), authentication should "just work".
    - If you're developing locally, the easiest way to authenticate is using the `Google
      Cloud SDK <http://cloud.google.com/sdk>`_::

        $ gcloud auth application-default login

    - If you're running your application elsewhere, you should download a `service account
      <https://cloud.google.com/iam/docs/creating-managing-service-accounts#creating>`_
      JSON keyfile and point to it using an environment variable::

        $ export GOOGLE_APPLICATION_CREDENTIALS="/path/to/keyfile.json"


    **Local emulator**

    If you set the environment variable ``PUBSUB_EMULATOR_HOST=host:port``,
    then this will connect to a local Pub/Sub emulator.

    """

    class Config:
        project_id = Option(doc="Google Cloud project id.")
        topic_name = Option(doc="The Pub/Sub topic name to publish to.")
        timeout = Option(
            default="5",
            doc=(
                "The amount of time in seconds individual rpc calls to pubsub are "
                "allowed to take before giving up. This is passed to `PublisherOptions "
                "<https://cloud.google.com/python/docs/reference/pubsub/latest/google.cloud.pubsub_v1.types.PublisherOptions>`_. "
                "From 2018 through 2023 Mozilla's internal data platform's use of "
                "pubsub generally saw publish response times less than 150ms, and "
                "had one incident where response times were approximately 1 second. "
                "Based on that experience this has a default of 5 seconds."
            ),
            parser=float,
        )

    def __init__(self, config):
        super().__init__(config)

        self.project_id = self.config("project_id")
        self.topic_name = self.config("topic_name")

        if emulator := os.environ.get("PUBSUB_EMULATOR_HOST"):
            logger.debug(
                "PUBSUB_EMULATOR_HOST detected, connecting to emulator: %s",
                emulator,
            )
        self.publisher = PublisherClient(
            # publish messages immediately without queuing.
            batch_settings=BatchSettings(max_messages=1),
            # disable retry in favor of crashmover's retry and set rpc timeout
            publisher_options=PublisherOptions(
                retry=None, timeout=self.config("timeout")
            ),
        )

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
