# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging

from everett.manager import Option, parse_class

from antenna.app import register_for_verification
from antenna.ext.crashstorage_base import CrashStorageBase
from antenna.util import json_ordered_dumps


logger = logging.getLogger(__name__)


class S3CrashStorage(CrashStorageBase):
    """Save raw crash files to S3.

    This will save raw crash files to S3 in a pseudo-tree something like this:

    ::

        <BUCKET>
           v1/
               dump_names/
                   <CRASHID>
               <DUMPNAME>/
                   <CRASHID>
               raw_crash/
                   <YYYYMMDD>/
                       <CRASHID>

    """

    class Config:
        connection_class = Option(
            default="antenna.ext.s3.connection.S3Connection",
            parser=parse_class,
            doc="S3 connection class to use",
        )

    def __init__(self, config):
        self.config = config.with_options(self)
        self.connection = self.config("connection_class")(config)
        register_for_verification(self.verify_write_to_bucket)

    def get_components(self):
        """Return map of namespace -> component for traversing component tree."""
        return {"": self.connection}

    def verify_write_to_bucket(self):
        """Verify S3 bucket exists and can be written to."""
        self.connection.verify_write_to_bucket()

    def get_runtime_config(self, namespace=None):
        """Return generator for items in runtime configuration."""
        yield from super().get_runtime_config(namespace)

        yield from self.connection.get_runtime_config(namespace)

    def check_health(self, state):
        """Check connection health."""
        self.connection.check_health(state)

    def save_raw_crash(self, crash_id, raw_crash):
        """Save the raw crash and related dumps.

        .. Note::

           If you're saving the raw crash and dumps, make sure to save the raw
           crash last.

        :arg str crash_id: The crash id as a string.
        :arg dict raw_crash: dict The raw crash as a dict.

        :raises botocore.exceptions.ClientError: connection issues, permissions
            issues, bucket is missing, etc.

        """
        # FIXME(willkg): self.connection.save_file raises a
        # botocore.exceptions.ClientError if the perms aren't right. That needs
        # to surface to "this node is not healthy".

        # Save raw_crash
        self.connection.save_file(
            self._get_raw_crash_path(crash_id),
            json_ordered_dumps(raw_crash).encode("utf-8"),
        )

    def save_dumps(self, crash_id, dumps):
        """Save dump data.

        :arg str crash_id: The crash id
        :arg dict dumps: dump name -> dump

        :raises botocore.exceptions.ClientError: connection issues, permissions
            issues, bucket is missing, etc.

        """
        # Save dump_names even if there are no dumps
        self.connection.save_file(
            self._get_dump_names_path(crash_id),
            json_ordered_dumps(list(sorted(dumps.keys()))).encode("utf-8"),
        )

        # Save dumps
        for dump_name, dump in dumps.items():
            self.connection.save_file(
                self._get_dump_name_path(crash_id, dump_name), dump
            )

    def save_crash(self, crash_report):
        """Save crash data."""
        crash_id = crash_report.crash_id
        raw_crash = crash_report.raw_crash
        dumps = crash_report.dumps

        # Save dumps first
        self.save_dumps(crash_id, dumps)

        # Save raw crash
        self.save_raw_crash(crash_id, raw_crash)
