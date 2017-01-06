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
    def __init__(self):
        self.errors = []

    def add_error(self, msg):
        self.errors.append(msg)

    def raw_crash_key(self, crash_id):
        return '/v2/raw_crash/{entropy}/{date}/{crashid}'.format(
            entropy=crash_id[0:3],
            date='20' + crash_id[-6:],
            crashid=crash_id
        )

    def dump_names_key(self, crash_id):
        return '/v1/dump_names/{crashid}'.format(
            crashid=crash_id
        )

    def dump_key(self, crash_id, name):
        return '/v1/{name}/{crashid}'.format(
            name=name,
            crashid=crash_id
        )

    def compare_item(self, key, a, values):
        if not isinstance(values, list):
            if a != values:
                self.add_error('%s: %s != %s' % (key, a, values))

        else:
            if a not in values:
                self.add_error('%s: %s not in %s' % (key, a, values))

    def verify_crash_data(self, crash_id, raw_crash, dumps, s3conn):
        # Fetch everything from S3
        s3_raw_crash = s3conn.get_object(self.raw_crash_key(crash_id), is_json=True)
        s3_dump_names = s3conn.get_object(self.dump_names_key(crash_id), is_json=True)
        s3_dumps = dict([
            (name, s3conn.get_object(self.dump_key(crash_id, name)))
            for name, dump in dumps.items()
        ])

        # Verify it
        self.compare_raw_crash(crash_id, raw_crash, dumps, s3_raw_crash, s3_dump_names, s3_dumps)
        self.compare_dump_data(crash_id, raw_crash, dumps, s3_raw_crash, s3_dump_names, s3_dumps)

    def compare_raw_crash(self, crash_id, raw_crash, dumps, s3_raw_crash, s3_dump_names, s3_dumps):
        # Go through and make sure the raw crash on s3 has all the data the
        # original raw crash had
        for key in raw_crash:
            self.compare_item(key, s3_raw_crash.get(key, None), raw_crash[key])

        # Now verify additional metadata

        # Crash id == uuid
        self.compare_item('uuid', s3_raw_crash.get('uuid', None), crash_id)

        try:
            float(s3_raw_crash.get('timestamp', None))
            # FIXME(willkg): Verify the value? Tt's a time.time() so there's no
            # timezone attached to it so who knows what it could be.
        except ValueError:
            self.add_error('timestamp: %s is not a float' % s3_raw_crash.get('timestamp', None))

        now = utc_now()
        submitted_timestamp = s3_raw_crash.get('submitted_timestamp', None)
        if submitted_timestamp is None:
            self.add_error('submitted_timestamp: %s is not valid' % submitted_timestamp)
        else:
            submitted_timestamp = isodate.parse_datetime(submitted_timestamp)
            # submitted_timestamp should be within 5 minutes of now. If not, then
            # it might still be right, but it's probably fishy.
            if not ((now - datetime.timedelta(minutes=5)) < submitted_timestamp < now):
                self.add_error('submitted_timestamp: %s is not within range %s -> %s' % (
                    submitted_timestamp, (now - datetime.timedelta(min=5)), now
                ))

        # percentage in the throttle rules is always either 10 or 100 for rules
        # that involve saving to s3.
        self.compare_item('percentage', s3_raw_crash.get('percentage', None), [10, 100])
        self.compare_item('legacy_processing', s3_raw_crash.get('legacy_processing', None), [0, 1])

        self.compare_item('type_tag', s3_raw_crash.get('type_tag', None), 'bp')

        # FIXME(willkg): we should verify the contents
        if 'dump_checksums' not in s3_raw_crash:
            self.add_error('dump_checksums: missing')

        # FIXME(willkg): Verify there isn't anything else in the s3_raw_crash
        # we didn't expect.

    def compare_dump_data(self, crash_id, raw_crash, dumps, s3_raw_crash, s3_dump_names, s3_dumps):
        compare(sorted(dumps.keys()), sorted(s3_dump_names))
        # FIXME(willkg): compare with dump_names

        # FIXME(willkg): compare dumps


def compare(a, b):
    def _compare(a, b):
        if type(a) != type(b):
            print('TypeError %s != %s' % (type(a), type(b)))
            return False

        if isinstance(a, dict):
            for key in a.keys():
                if key not in b:
                    print('ValueError %s not in %s' % (key, b))
                    return False
                if not _compare(a[key], b[key]):
                    print('%s != %s' % (a[key], b[key]))
                    return False

            if len(a) < len(b):
                print('ValueError %s < %s' % (a.keys(), b.keys()))
                return False

            return True

        if isinstance(a, (list, set)):
            for item_a, item_b in zip(a, b):
                if not _compare(item_a, item_b):
                    print('ValueError %s != %s' % (item_a, item_b))
                    return False

        return a == b
    return _compare(a, b)


class TestCompare:
    def test_none(self):
        assert compare(None, None) is True

    def test_int(self):
        assert compare(1, 1) is True
        assert compare(1, 2) is False

    @pytest.mark.parametrize('a,b,expected', [
        ([], [], True),
        ([1], [1], True),
        ([1, 2, 3, 'abc'], [1, 2, 3, 'abc'], True),
        ([1, 2], [2, 1], False)
    ])
    def test_list(self, a, b, expected):
        assert compare(a, b) is expected
        assert compare(b, a) is expected

    @pytest.mark.parametrize('a,b,expected', [
        (set(), set(), True),
        ({1}, {1}, True),
        ({1, 2, 3, 'abc'}, {1, 2, 3, 'abc'}, True),
        ({1, 2}, {2, 1}, True),
    ])
    def test_set(self, a, b, expected):
        assert compare(a, b) is expected
        assert compare(b, a) is expected

    @pytest.mark.parametrize('a,b,expected', [
        ({}, {}, True),
        ({1: 2}, {1: 2}, True),
        ({1: 2, 3: 4}, {1: 2, 3: 4}, True),
        ({1: 2}, {1: 3}, False),
    ])
    def test_dict(self, a, b, expected):
        assert compare(a, b) is expected
        assert compare(b, a) is expected

    def test_crash_like(self):
        obj_a = {
            'ProductName': 'Firefox',
            'Version': '1',
            'BuildID': '20160728203720'
        }
        obj_b = {
            'ProductName': 'Firefox',
            'Version': '2',
            'BuildID': '20160728203720'
        }
        assert compare(obj_a, obj_b) is False


def content_to_crashid(content):
    if not isinstance(content, str):
        content = str(content, encoding='utf-8')

    crash_id = content.strip()
    crash_id = crash_id[len('CrashID=bp-'):]
    return crash_id


class TestPostCrash:
    def test_regular(self, posturl, s3conn, crash_generator):
        """Post a valid crash and verify the contents made it to S3"""
        raw_crash, dumps = crash_generator.generate()
        crash_payload = mini_poster.assemble_crash_payload(raw_crash, dumps)
        resp = mini_poster.post_crash(posturl, crash_payload, dumps)

        # Sleep 1s to give Antenna time to save things
        time.sleep(1)

        crash_id = content_to_crashid(resp.content)
        logger.debug('Crash ID is: %s', crash_id)

        verifier = CrashVerifier()
        verifier.verify_crash_data(crash_id, raw_crash, dumps, s3conn)

        if verifier.errors:
            for error in verifier.errors:
                logger.error(error)

        assert not verifier.errors

    def test_compressed_crash(self, posturl, s3conn, crash_generator):
        """Post a compressed crash and verify contents made it to s3"""
        raw_crash, dumps = crash_generator.generate()
        crash_payload = mini_poster.assemble_crash_payload(raw_crash, dumps)
        resp = mini_poster.post_crash(posturl, crash_payload, compressed=True)

        # Sleep 1s to give Antenna time to save things
        time.sleep(1)

        crash_id = content_to_crashid(resp.content)
        logger.debug('Crash ID is: %s', crash_id)

        verifier = CrashVerifier()
        verifier.verify_crash_data(crash_id, raw_crash, dumps, s3conn)

        if verifier.errors:
            for error in verifier.errors:
                logger.error(error)

        assert not verifier.errors
