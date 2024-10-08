# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import datetime
import logging
import time

import isodate
import pytest

from testlib import mini_poster


LOGGER = logging.getLogger(__name__)


def utc_now():
    return datetime.datetime.now(isodate.UTC)


def content_to_crashid(content):
    if not isinstance(content, str):
        content = str(content, encoding="utf-8")

    crash_id = content.strip()
    crash_id = crash_id[len("CrashID=bp-") :]
    return crash_id


# Gives Antenna time to save things before we check
SLEEP_TIME = 5


class TestPostCrash:
    def test_regular(
        self,
        posturl,
        storage_helper,
        queue_helper,
        crash_generator,
        crash_verifier,
        postcheck,
    ):
        """Post a valid crash and verify the contents made it to storage."""
        if not postcheck:
            pytest.skip("no access to storage")

        raw_crash, dumps = crash_generator.generate()
        crash_payload = mini_poster.assemble_crash_payload_dict(raw_crash, dumps)
        resp = mini_poster.post_crash(posturl, crash_payload, dumps)

        # Sleep to give Antenna time to save things
        time.sleep(SLEEP_TIME)

        crash_id = content_to_crashid(resp.content)
        LOGGER.debug("Crash ID is: %s", crash_id)
        LOGGER.debug("Storage helper: %s", storage_helper.get_config())

        # Verify stored and published crash data
        crash_verifier.verify_stored_data(crash_id, raw_crash, dumps, storage_helper)
        crash_verifier.verify_published_data(crash_id, queue_helper)

    def test_compressed_crash(
        self,
        posturl,
        storage_helper,
        queue_helper,
        crash_generator,
        crash_verifier,
        postcheck,
    ):
        """Post a compressed crash and verify contents made it to storage."""
        if not postcheck:
            pytest.skip("no access to storage")

        raw_crash, dumps = crash_generator.generate()
        crash_payload = mini_poster.assemble_crash_payload_dict(raw_crash, dumps)
        resp = mini_poster.post_crash(posturl, crash_payload, compressed=True)

        # Sleep to give Antenna time to save things
        time.sleep(SLEEP_TIME)

        crash_id = content_to_crashid(resp.content)
        LOGGER.debug("Crash ID is: %s", crash_id)
        LOGGER.debug("Storage helper: %s", storage_helper.get_config())

        # Verify stored and published crash data
        crash_verifier.verify_stored_data(crash_id, raw_crash, dumps, storage_helper)
        crash_verifier.verify_published_data(crash_id, queue_helper)
