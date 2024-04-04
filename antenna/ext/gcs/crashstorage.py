# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
import os
import uuid

from everett.manager import Option
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage

from antenna.app import register_for_verification
from antenna.ext.crashstorage_base import CrashStorageBase
from antenna.util import get_date_from_crash_id, json_ordered_dumps

logger = logging.getLogger(__name__)


def generate_test_filepath():
    """Generate a unique-ish test filepath."""
    return "test/testfile-%s.txt" % uuid.uuid4()


class GcsCrashStorage(CrashStorageBase):
    """Save raw crash files to GCS.

    This will save raw crash files to GCS in a pseudo-tree something like this:

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

    If you set the environment variable ``STORAGE_EMULATOR_HOST=http://host:port``,
    then this will connect to a local GCS emulator.


    """

    class Config:
        bucket_name = Option(
            doc=(
                "Google Cloud Storage bucket to save to. Note that the bucket must "
                "already have been created."
            ),
        )

    def __init__(self, config):
        self.config = config.with_options(self)
        self.bucket = self.config("bucket_name")

        if emulator := os.environ.get("STORAGE_EMULATOR_HOST"):
            logger.debug(
                "STORAGE_EMULATOR_HOST detected, connecting to emulator: %s",
                emulator,
            )
            self.client = storage.Client(
                credentials=AnonymousCredentials(),
                project="test",
            )
        else:
            self.client = storage.Client()

        register_for_verification(self.verify_write_to_bucket)

    def _save_file(self, path, data):
        """Save a single file to GCS.

        :arg str path: the path to save to
        :arg bytes data: the data to save

        """
        bucket = self.client.get_bucket(self.bucket)
        blob = bucket.blob(path)
        blob.upload_from_string(data)

    def verify_write_to_bucket(self):
        """Verify GCS bucket exists and can be written to."""
        self._save_file(generate_test_filepath(), b"test")

    def check_health(self, state):
        """Check GCS connection health."""
        try:
            # get the bucket to verify GCS is up and we can connect to it.
            self.client.get_bucket(self.bucket)
        except Exception as exc:
            state.add_error("GcsCrashStorage", repr(exc))

    def _get_raw_crash_path(self, crash_id):
        return "v1/raw_crash/{date}/{crash_id}".format(
            date=get_date_from_crash_id(crash_id),
            crash_id=crash_id,
        )

    def _get_dump_names_path(self, crash_id):
        return f"v1/dump_names/{crash_id}"

    def _get_dump_name_path(self, crash_id, dump_name):
        if dump_name in (None, "", "upload_file_minidump"):
            dump_name = "dump"

        return "v1/{dump_name}/{crash_id}".format(
            dump_name=dump_name, crash_id=crash_id
        )

    def save_raw_crash(self, crash_id, raw_crash):
        """Save the raw crash and related dumps.

        :arg str crash_id: The crash id as a string.
        :arg dict raw_crash: dict The raw crash as a dict.

        """
        self._save_file(
            self._get_raw_crash_path(crash_id),
            json_ordered_dumps(raw_crash).encode("utf-8"),
        )

    def save_dumps(self, crash_id, dumps):
        """Save dump data.

        :arg str crash_id: The crash id
        :arg dict dumps: dump name -> dump

        """
        # Save dump_names even if there are no dumps
        self._save_file(
            self._get_dump_names_path(crash_id),
            json_ordered_dumps(list(sorted(dumps.keys()))).encode("utf-8"),
        )

        # Save dumps
        for dump_name, dump in dumps.items():
            self._save_file(self._get_dump_name_path(crash_id, dump_name), dump)

    def save_crash(self, crash_report):
        """Save crash data."""
        crash_id = crash_report.crash_id
        raw_crash = crash_report.raw_crash
        dumps = crash_report.dumps

        self.save_dumps(crash_id, dumps)
        self.save_raw_crash(crash_id, raw_crash)
