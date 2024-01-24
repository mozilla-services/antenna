# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
import random

import boto3
from botocore.client import ClientError
from everett.manager import Option
import gevent

from antenna.app import register_for_verification
from antenna.ext.crashpublish_base import CrashPublishBase
from antenna.util import retry


logger = logging.getLogger(__name__)


def wait_times_connect():
    """Return generator for wait times with jitter between failed connection attempts."""
    for i in [5] * 5:
        yield i + random.uniform(-2, 2)  # nosec


class SQSCrashPublish(CrashPublishBase):
    """Publisher to AWS SQS.

    **Required AWS SQS things**

    When configuring credentials for this crashpublish object, you can do one of two
    things:

    1. provide ``ACCESS_KEY`` and ``SECRET_ACCESS_KEY`` in the configuration, OR
    2. use one of the other methods described in the boto3 docs
       https://boto3.readthedocs.io/en/latest/guide/configuration.html#configuring-credentials

    You also need to create an AWS SQS standard queue with the following settings:

    ==========================  =========
    Setting                     Value
    ==========================  =========
    Default Visibility Timeout  5 minutes
    Message Retention Period    *default*
    Maximum Message Size        *default*
    Delivery Delay              *default*
    Receive Message Wait Time   *default*
    ==========================  =========

    The AWS credentials that Antenna is configured with must have the following
    Amazon SQS permissions on the SQS queue you created:

    * ``sqs:GetQueueUrl``

      Antenna needs to convert a queue name to a queue url. This requires the
      ``sqs:GetQueueUrl``

    * ``sqs:SendMessage``

      Antenna sends messages to a queue--this is how it publishes crash ids.
      This requires the ``sqs:SendMessage`` permission.

    If something isn't configured correctly, then Antenna may not start.


    **Verification**

    This component verifies that it can publish to the queue by publishing a
    fake crash id of ``test``. Downstream consumers should ignore these.

    """

    class Config:
        access_key = Option(
            default="",
            alternate_keys=["root:aws_access_key_id"],
            doc=(
                "AWS SQS access key. You can also specify AWS_ACCESS_KEY_ID which is "
                "the env var used by boto3."
            ),
        )
        secret_access_key = Option(
            default="",
            alternate_keys=["root:aws_secret_access_key"],
            doc=(
                "AWS SQS secret access key. You can also specify AWS_SECRET_ACCESS_KEY "
                "which is the env var used by boto3."
            ),
        )
        region = Option(
            default="us-west-2",
            alternate_keys=["root:s3_region"],
            doc="AWS region to connect to. For example, ``us-west-2``",
        )
        endpoint_url = Option(
            default="",
            alternate_keys=["root:s3_endpoint_url"],
            doc=(
                "endpoint_url to connect to; None if you are connecting to AWS. For "
                "example, ``http://localhost:4569/``."
            ),
        )
        queue_name = Option(doc="The AWS SQS queue name.")

    def __init__(self, config):
        super().__init__(config)

        self.queue_name = self.config("queue_name")
        self.client = self._build_client()
        self.queue_url = self.client.get_queue_url(QueueName=self.queue_name)[
            "QueueUrl"
        ]

        register_for_verification(self.verify_queue)

    @retry(
        retryable_exceptions=[
            # FIXME(willkg): Seems like botocore always raises ClientError
            # which is unhelpful for granularity purposes.
            ClientError,
            # This raises a ValueError "invalid endpoint" if it has problems
            # getting the s3 credentials and then tries "s3..amazonaws.com"--we
            # want to retry that, too.
            ValueError,
        ],
        wait_time_generator=wait_times_connect,
        sleep_function=gevent.sleep,
        module_logger=logger,
    )
    def _build_client(self):
        # Either they provided ACCESS_KEY and SECRET_ACCESS_KEY in which case
        # we use those, or they didn't in which case boto3 pulls credentials
        # from one of a myriad of other places.
        # https://boto3.readthedocs.io/en/latest/guide/configuration.html#configuring-credentials
        session_kwargs = {}
        if self.config("access_key") and self.config("secret_access_key"):
            session_kwargs["aws_access_key_id"] = self.config("access_key")
            session_kwargs["aws_secret_access_key"] = self.config("secret_access_key")
        session = boto3.session.Session(**session_kwargs)

        kwargs = {
            "service_name": "sqs",
            "region_name": self.config("region"),
        }
        if self.config("endpoint_url"):
            kwargs["endpoint_url"] = self.config("endpoint_url")

        return session.client(**kwargs)

    def verify_queue(self):
        """Verify queue can be published to by publishing fake crash id."""
        self.client.send_message(QueueUrl=self.queue_url, MessageBody="test")

    def check_health(self, state):
        """Check AWS SQS connection health."""
        try:
            self.client.get_queue_url(QueueName=self.queue_name)
        except Exception as exc:
            state.add_error("SQSCrashPublish", repr(exc))

    def publish_crash(self, crash_report):
        """Publish a crash id to an AWS SQS queue."""
        crash_id = crash_report.crash_id
        self.client.send_message(QueueUrl=self.queue_url, MessageBody=crash_id)
