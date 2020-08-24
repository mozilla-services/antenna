# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import logging
import time

import isodate
import pytest

from testlib import mini_poster


logger = logging.getLogger(__name__)


def utc_now():
    return datetime.datetime.now(isodate.UTC)


class CrashVerifier:
    def raw_crash_key(self, crash_id):
        return "v2/raw_crash/{entropy}/{date}/{crashid}".format(
            entropy=crash_id[0:3], date="20" + crash_id[-6:], crashid=crash_id
        )

    def dump_names_key(self, crash_id):
        return "v1/dump_names/{crashid}".format(crashid=crash_id)

    def dump_key(self, crash_id, name):
        if name in (None, "", "upload_file_minidump"):
            name = "dump"

        return "v1/{name}/{crashid}".format(name=name, crashid=crash_id)

    def verify_stored_data(self, crash_id, raw_crash, dumps, s3conn):
        # Verify the raw crash file made it
        key = self.raw_crash_key(crash_id)
        assert key in s3conn.list_objects(prefix=key)

        # Verify the dump_names file made it
        key = self.dump_names_key(crash_id)
        assert key in s3conn.list_objects(prefix=key)

        # Verify the dumps made it
        for name, dump in dumps.items():
            key = self.dump_key(crash_id, name)
            assert key in s3conn.list_objects(prefix=key)

    def verify_published_data(self, crash_id, sqshelper):
        # Verify crash id was published--this might pick up a bunch of stuff,
        # so we just verify it's one of the things we picked up
        assert crash_id in sqshelper.list_crashids()


def content_to_crashid(content):
    if not isinstance(content, str):
        content = str(content, encoding="utf-8")

    crash_id = content.strip()
    crash_id = crash_id[len("CrashID=bp-") :]
    return crash_id


# Gives Antenna time to save things before we check
SLEEP_TIME = 5


class TestPostCrash:
    def test_regular(self, posturl, s3conn, sqshelper, crash_generator, postcheck):
        """Post a valid crash and verify the contents made it to S3."""
        if not postcheck:
            pytest.skip("no access to S3")

        raw_crash, dumps = crash_generator.generate()
        crash_payload = mini_poster.assemble_crash_payload_dict(raw_crash, dumps)
        resp = mini_poster.post_crash(posturl, crash_payload, dumps)

        # Sleep to give Antenna time to save things
        time.sleep(SLEEP_TIME)

        crash_id = content_to_crashid(resp.content)
        logger.debug("Crash ID is: %s", crash_id)
        logger.debug("S3conn: %s", s3conn.get_config())

        # Verify stored and published crash data
        verifier = CrashVerifier()
        verifier.verify_stored_data(crash_id, raw_crash, dumps, s3conn)
        verifier.verify_published_data(crash_id, sqshelper)

    def test_compressed_crash(self, posturl, s3conn, sqshelper, crash_generator, postcheck):
        """Post a compressed crash and verify contents made it to S3."""
        if not postcheck:
            pytest.skip("no access to S3")

        raw_crash, dumps = crash_generator.generate()
        crash_payload = mini_poster.assemble_crash_payload_dict(raw_crash, dumps)
        resp = mini_poster.post_crash(posturl, crash_payload, compressed=True)

        # Sleep to give Antenna time to save things
        time.sleep(SLEEP_TIME)

        crash_id = content_to_crashid(resp.content)
        logger.debug("Crash ID is: %s", crash_id)
        logger.debug("S3conn: %s", s3conn.get_config())

        # Verify stored and published crash data
        verifier = CrashVerifier()
        verifier.verify_stored_data(crash_id, raw_crash, dumps, s3conn)
        verifier.verify_published_data(crash_id, sqshelper)
