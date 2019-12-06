# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import io
import logging
import random
import uuid

import boto3
from botocore.client import ClientError, Config
from everett.component import ConfigOptions, RequiredConfigMixin
import gevent

from antenna.util import retry


logger = logging.getLogger(__name__)


def generate_test_filepath():
    """Generate a unique-ish test filepath."""
    return "test/testfile-%s.txt" % uuid.uuid4()


def wait_times_connect():
    """Return generator for wait times between failed connection attempts.

    We have this problem where we're binding IAM credentials to the EC2 node
    and on startup when boto3 goes to get the credentials, it fails for some
    reason and then degrades to hitting the https://s3..amazonaws.net/
    endpoint and then fails because that's not a valid endpoint.

    This sequence increases the wait times and adds some jitter.

    """
    for i in [5] * 5:
        yield i + random.uniform(-2, 2)  # nosec


def wait_times_save():
    """Return generator for wait times between failed save attempts.

    This waits 2 seconds between failed save attempts for 5 iterations and then
    gives up.

    """
    for i in [2, 2, 2, 2, 2]:
        yield i


class S3Connection(RequiredConfigMixin):
    """Connection object for S3.

    **Credentials and permissions**

    When configuring this connection object, you can do one of two things:

    1. provide ``ACCESS_KEY`` and ``SECRET_ACCESS_KEY`` in the configuration, OR
    2. use one of the other methods described in the boto3 docs
       http://boto3.readthedocs.io/en/latest/guide/configuration.html#configuring-credentials


    The AWS credentials that Antenna is configured with must have the following
    Amazon S3 permissions:

    * ``s3:ListBucket``

      Antenna periodically checks its health and during that health check, it
      will HEAD the S3 Bucket. This requires ``s3:ListBucket`` permissions.

    * ``s3:PutObject``

      This permission is used to save items to the bucket.

      Additionally, at startup, Antenna will attempt to save a test file to the
      bucket. If that fails, then this will raise an error and will halt
      startup.


    **Retrying saves**

    When saving crashes, this connection will retry saving several times. Then
    give up. The crashmover coroutine will put the crash back in the queue to
    retry later. Crashes are never thrown out.

    """

    required_config = ConfigOptions()
    required_config.add_option(
        "access_key",
        default="",
        alternate_keys=["root:aws_access_key_id"],
        doc=(
            "AWS access key. You can also specify AWS_ACCESS_KEY_ID which is "
            "the env var used by boto3."
        ),
    )
    required_config.add_option(
        "secret_access_key",
        default="",
        alternate_keys=["root:aws_secret_access_key"],
        doc=(
            "AWS secret access key. You can also specify AWS_SECRET_ACCESS_KEY "
            "which is the env var used by boto3."
        ),
    )
    required_config.add_option(
        "region",
        default="us-west-2",
        alternate_keys=["root:s3_region"],
        doc="AWS region to connect to. For example, ``us-west-2``",
    )
    required_config.add_option(
        "endpoint_url",
        default="",
        alternate_keys=["root:s3_endpoint_url"],
        doc=(
            "endpoint_url to connect to; None if you are connecting to AWS. For "
            "example, ``http://localhost:4569/``."
        ),
    )
    required_config.add_option(
        "bucket_name",
        doc=(
            "AWS S3 bucket to save to. Note that the bucket must already have been "
            "created and must be in the region specified by ``region``."
        ),
    )

    def __init__(self, config):
        self.config = config.with_options(self)
        self.bucket = self.config("bucket_name")
        self.client = self._build_client()

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
        # http://boto3.readthedocs.io/en/latest/guide/configuration.html#configuring-credentials
        session_kwargs = {}
        if self.config("access_key") and self.config("secret_access_key"):
            session_kwargs["aws_access_key_id"] = self.config("access_key")
            session_kwargs["aws_secret_access_key"] = self.config("secret_access_key")
        session = boto3.session.Session(**session_kwargs)

        kwargs = {
            "service_name": "s3",
            "region_name": self.config("region"),
            # NOTE(willkg): We use path-style because that lets us have dots in
            # our bucket names and use SSL.
            "config": Config(s3={"addressing_style": "path"}),
        }
        if self.config("endpoint_url"):
            kwargs["endpoint_url"] = self.config("endpoint_url")

        return session.client(**kwargs)

    def verify_write_to_bucket(self):
        """Verify S3 bucket exists and can be written to.

        This will do multiple attempts and then give up and throw an exception.

        """
        self.client.upload_fileobj(
            Fileobj=io.BytesIO(b"test"),
            Bucket=self.bucket,
            Key=generate_test_filepath(),
        )

    def check_health(self, state):
        """Check S3 connection health."""
        try:
            # HEAD the bucket to verify S3 is up and we can connect to it.
            self.client.head_bucket(Bucket=self.bucket)
        except Exception as exc:
            state.add_error("S3Connection", repr(exc))

    @retry(
        retryable_exceptions=[
            # FIXME(willkg): Seems like botocore always raises ClientError
            # which is unhelpful for granularity purposes.
            ClientError
        ],
        wait_time_generator=wait_times_save,
        sleep_function=gevent.sleep,
        module_logger=logger,
    )
    def save_file(self, path, data):
        """Save a single file to S3.

        This will retry a handful of times in short succession so as to deal
        with some amount of fishiness. After that, the caller should retry
        saving after a longer period of time.

        :arg str path: the path to save to

        :arg bytes data: the data to save

        :raises botocore.exceptions.ClientError: connection issues, permissions
            issues, bucket is missing, etc.

        """
        if not isinstance(data, bytes):
            raise TypeError("data argument must be bytes")

        self.client.upload_fileobj(
            Fileobj=io.BytesIO(data), Bucket=self.bucket, Key=path
        )
