#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""With fakes3, we need to create the bucket before we can use it. This script
makes that easier.

To use:

1. First in one terminal, start fakes3 container::

       $ docker-compose up fakes3

2. In a second terminal, start a web container and run the script::

       $ docker-compose run web bash
       app@...$ ANTENNA_ENV=prod.env bin/create_fakes3_bucket.py


It'll check to see if the bucket is already created and if so, it won't do
anything.

It'll throw an error if something unexpected happened.

.. NOTE::

   Don't use this for creating buckets in AWS S3. You should use the console
   for that.

"""

import os
import sys

from botocore.exceptions import ClientError
from everett.manager import ConfigManager, ConfigEnvFileEnv, ConfigOSEnv

sys.path.insert(0, os.getcwd())  # noqa

from antenna.external.s3.connection import S3Connection


def main(args):
    # Build configuration object just like we do in Antenna.
    config = ConfigManager([
        # Pull configuration from env file specified as ANTENNA_ENV
        ConfigEnvFileEnv([os.environ.get('ANTENNA_ENV')]),
        # Pull configuration from environment variables
        ConfigOSEnv()
    ])

    # We create it in the crashstorage namespace because that's how Antenna
    # uses it. This makes it easier to use existing configuration.
    conn = S3Connection(config.with_namespace('crashstorage'), no_verify=True)

    # First, check to see if the bucket is already created.
    try:
        conn.verify_configuration()
        print('Bucket %s exists.' % conn.bucket)

    except ClientError as exc:
        if 'HeadBucket operation: Not Found' in str(exc):
            # Create the bucket.
            conn._create_bucket()
            print('Bucket %s created.' % conn.bucket)
        else:
            raise


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
