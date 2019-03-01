#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""When doing local development, we need to create the bucket before we can use
it. This script makes that easier.

In order for this script to run, you must have the localstack-s3 container
running.

If a bucket exists, it won't do anything.

It'll throw an error if something unexpected happened.

.. Note::

   Don't use this for creating buckets in AWS S3. You should use the console
   for that.

"""

import logging
import os
import sys

from botocore.exceptions import ClientError
from everett.manager import ConfigManager, ConfigEnvFileEnv, ConfigOSEnv

sys.path.insert(0, os.getcwd())  # noqa

from antenna.ext.s3.connection import S3Connection


def _log_everything():
    # Set up all the debug logging for grossest possible output
    from http.client import HTTPConnection
    HTTPConnection.debuglevel = 1

    logging.getLogger('requests').setLevel(logging.DEBUG)
    logging.getLogger('requests.packages.urllib3').setLevel(logging.DEBUG)


# _log_everything()


def main(args):
    # Build configuration object just like we do in Antenna.
    config = ConfigManager([
        # Pull configuration from environment variables
        ConfigOSEnv()
    ])

    # We create it in the crashstorage namespace because that's how Antenna
    # uses it. This makes it easier to use existing configuration.
    conn = S3Connection(config.with_namespace('crashstorage'))

    # First, check to see if the bucket is already created.
    try:
        print('Checking to see if bucket "%s" exists...' % conn.bucket)
        conn.verify_bucket_exists()
        print('Bucket exists.')

    except ClientError as exc:
        print(str(exc))
        if 'HeadBucket operation: Not Found' in str(exc):
            print('Bucket not found. Creating %s ...' % conn.bucket)
            conn._create_bucket()
            print('Bucket created.')
        else:
            raise


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
