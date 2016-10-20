# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import io
import logging

import boto3
from botocore.client import ClientError, Config
from everett.component import ConfigOptions, RequiredConfigMixin
import gevent

from antenna.util import retry


logger = logging.getLogger(__name__)


class S3Connection(RequiredConfigMixin):
    """Connection object for S3

    When configuring this connection object, you can do one of two things:

    1. provide ``ACCESS_KEY`` and ``SECRET_ACCESS_KEY`` in the configuration
    2. use one of the other methods described in the boto3 docs
       http://boto3.readthedocs.io/en/latest/guide/configuration.html#configuring-credentials

    When Antenna starts up, ``S3Connection`` will call ``HEAD`` on the bucket
    verifying the bucket exists, the endpoint url is good, it's accessible and
    the credentials are valid.

    If that fails, then this will raise an error and will halt startup.

    .. Warning::

       This does not verify that it has write permissions to the bucket. Test
       your configuration by sending a test crash and watch your logs at
       startup!

       Permission errors are a retryable error, so this component will keep
       retrying forever.


    When saving crashes, this connection will retry forever.

    """
    required_config = ConfigOptions()
    required_config.add_option(
        'access_key',
        default='',
        alternate_keys=['root:s3_access_key'],
        doc='AWS S3 access key'
    )
    required_config.add_option(
        'secret_access_key',
        default='',
        alternate_keys=['root:s3_secret_access_key'],
        doc='AWS S3 secret access key'
    )
    required_config.add_option(
        'region',
        default='us-west-2',
        alternate_keys=['root:s3_region'],
        doc='AWS S3 region to connect to. For example, ``us-west-2``'
    )
    required_config.add_option(
        'endpoint_url',
        default='',
        alternate_keys=['root:s3_endpoint_url'],
        doc=(
            'endpoint_url to connect to; None if you are connecting to AWS. For '
            'example, ``http://localhost:4569/``.'
        )
    )
    required_config.add_option(
        'bucket_name',
        doc=(
            'AWS S3 bucket to save to. Note that the bucket must already have been '
            'created and must be in the region specified by ``region``.'
        )
    )

    def __init__(self, config, no_verify=False):
        self.config = config.with_options(self)
        self.bucket = self.config('bucket_name')
        self.client = self._build_client()

        if not no_verify:
            # This will throw an exception on startup if things aren't right. The
            # thinking being that it's better to crash at startup rather than get
            # into a state where we're handling incoming crashes but can't do
            # anything with them.
            self.verify_configuration()

    def _build_client(self):
        # Either they provided ACCESS_KEY and SECRET_ACCESS_KEY in which case
        # we use those, or they didn't in which case boto3 pulls credentials
        # from one of a myriad of other places.
        # http://boto3.readthedocs.io/en/latest/guide/configuration.html#configuring-credentials
        session_kwargs = {}
        if self.config('access_key') and self.config('secret_access_key'):
            session_kwargs['aws_access_key_id'] = self.config('access_key')
            session_kwargs['aws_secret_access_key'] = self.config('secret_access_key')
        session = boto3.session.Session(**session_kwargs)

        kwargs = {
            'service_name': 's3',
            'region_name': self.config('region'),
            # NOTE(willkg): We use path-style because that lets us have dots in
            # our bucket names and use SSL.
            'config': Config(s3={'addressing_style': 'path'})
        }
        if self.config('endpoint_url'):
            kwargs['endpoint_url'] = self.config('endpoint_url')

        return session.client(**kwargs)

    def verify_configuration(self):
        # Verify the bucket exists and that we can access it with our
        # credentials. This doesn't verify we can write to it--to do that we'd
        # either need to orphan a gazillion files or we'd also need DELETE
        # permission.
        self.client.head_bucket(Bucket=self.bucket)

    def _create_bucket(self):
        # NOTE(willkg): Don't use this except with fakes3 and dev environments.
        self.client.create_bucket(Bucket=self.bucket)

    def check_health(self, state):
        try:
            self.verify_configuration()
        except Exception as exc:
            state.add_error(self, repr(exc))

    @retry(
        retryable_exceptions=[
            # FIXME(willkg): Seems like botocore always raises ClientError
            # which is unhelpful for granularity purposes.
            ClientError,
        ],
        sleep_function=gevent.sleep,
        module_logger=logger,
    )
    def save_file(self, path, data):
        if not isinstance(data, bytes):
            raise TypeError('data argument must be bytes')

        self.client.upload_fileobj(
            Fileobj=io.BytesIO(data),
            Bucket=self.bucket,
            Key=path,
        )

    def load_file(self, path):
        # FIXME(willkg): implement this
        pass
