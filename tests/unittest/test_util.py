# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from datetime import datetime

from freezegun import freeze_time
import pytest

from antenna.util import (
    MaxAttemptsError,
    create_crash_id,
    get_date_from_crash_id,
    get_throttle_from_crash_id,
    get_version_info,
    isoformat_to_time,
    retry,
    sanitize_dump_name,
    utc_now,
    validate_crash_id,
)


def test_utc_now():
    res = utc_now()
    assert res.strftime("%Z") == "UTC"
    assert res.strftime("%z") == "+0000"
    assert res.tzinfo


@pytest.mark.parametrize(
    "data, expected",
    [
        # Good dates return good times
        ("2011-09-06T00:00:00+00:00", 1315267200.0),
        # Bad data returns 0.0
        ("foo", 0.0),
    ],
)
def test_isoformat_to_time(data, expected):
    assert isoformat_to_time(data) == expected


def test_get_version_info(tmpdir):
    fn = tmpdir.join("/version.json")
    fn.write_text(
        '{"commit": "d6ac5a5d2acf99751b91b2a3ca651d99af6b9db3"}', encoding="utf-8"
    )

    assert get_version_info(str(tmpdir)) == {
        "commit": "d6ac5a5d2acf99751b91b2a3ca651d99af6b9db3"
    }


@freeze_time("2011-09-06 00:00:00", tz_offset=0)
def test_crash_id():
    """Tests creating crash ids"""
    crash_id = create_crash_id()

    assert get_date_from_crash_id(crash_id) == "20110906"
    assert (
        get_date_from_crash_id(crash_id, as_datetime=True).strftime("%Y%m%d")
        == "20110906"
    )

    # Defaults to 1
    assert get_throttle_from_crash_id(crash_id) == 1


def test_crash_id_with_throttle():
    crash_id = create_crash_id(throttle_result=0)

    assert get_throttle_from_crash_id(crash_id) == 0


def test_crash_id_with_date():
    """Tests creating a crash id with a timestamp"""
    crash_id = create_crash_id(datetime(2016, 10, 4))

    assert get_date_from_crash_id(crash_id) == "20161004"


@pytest.mark.parametrize(
    "data, strict, expected",
    [
        # Test shape
        ("", True, False),
        ("aaa", True, False),
        ("de1bb258cbbf4589a67334f800160918", True, False),
        ("DE1BB258-CBBF-4589-A673-34F800160918", True, False),
        ("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", True, False),
        ("00000000-0000-0000-0000-000000000000", True, True),
        # Test throttle character
        ("de1bb258-cbbf-4589-a673-34f800160918", True, True),
        ("de1bb258-cbbf-4589-a673-34f801160918", True, True),
        ("de1bb258-cbbf-4589-a673-34f802160918", True, False),
        ("de1bb258-cbbf-4589-a673-34f802160918", False, True),
    ],
)
def test_validate_crash_id(data, strict, expected):
    assert validate_crash_id(data, strict=strict) == expected


@pytest.mark.parametrize(
    "data, expected",
    [
        ("", ""),
        ("dump_name", "dump_name"),
        ("dump", "dump"),
        ("upload_file_minidump", "upload_file_minidump"),
        ("upload_file_minidump_browser", "upload_file_minidump_browser"),
        ("upload_file_minidump_content", "upload_file_minidump_content"),
        ("upload_file_minidump_flash1", "upload_file_minidump_flash1"),
        ("upload_file_minidump_flash2", "upload_file_minidump_flash2"),
        # Sanitize non-ascii characters
        ("upload\u0394_file_minidump", "upload_file_minidump"),
        ("upload_file_m\xef\xbf\xbdnidump", "upload_file_mnidump"),
    ],
)
def test_sanitize_dump_name(data, expected):
    assert sanitize_dump_name(data) == expected


def make_fake_sleep():
    sleeps = []

    def _fake_sleep(attempt):
        sleeps.append(attempt)

    _fake_sleep.sleeps = sleeps
    return _fake_sleep


class Test_retry:
    """Tests for the retry decorator"""

    def test_retry_returns_correct_value(self):
        @retry()
        def some_thing():
            return 1

        assert some_thing() == 1

    def test_retryable_exceptions(self):
        # This will fail on the first attempt and raise MyException because MyException
        # is not in the list of retryable exceptions
        class MyException(Exception):
            pass

        fake_sleep = make_fake_sleep()

        @retry(retryable_exceptions=ValueError, sleep_function=make_fake_sleep)
        def some_thing():
            raise MyException

        with pytest.raises(MyException):
            some_thing()
        assert fake_sleep.sleeps == []

        # This will fail on the first attempt because MyException is not in the list of
        # retryable exceptions
        fake_sleep = make_fake_sleep()

        @retry(retryable_exceptions=[ValueError, IndexError], sleep_function=fake_sleep)
        def some_thing():
            raise MyException

        with pytest.raises(MyException):
            some_thing()
        assert fake_sleep.sleeps == []

        # This will retry until the max attempts and then raise MaxAttemptsError--the
        # actual exception is chained
        fake_sleep = make_fake_sleep()

        @retry(retryable_exceptions=ValueError, sleep_function=fake_sleep)
        def some_thing():
            raise ValueError

        with pytest.raises(MaxAttemptsError):
            some_thing()
        assert fake_sleep.sleeps == [2, 2, 2, 2, 2]

    def test_retryable_return(self):
        # Will keep retrying until max_attempts and then raise an error that includes
        # the last function return
        def is_not_200(ret):
            return ret != 200

        fake_sleep = make_fake_sleep()

        @retry(retryable_return=is_not_200, sleep_function=fake_sleep)
        def some_thing():
            return 404

        with pytest.raises(MaxAttemptsError) as excinfo:
            some_thing()

        assert excinfo.value.return_value == 404
        assert len(fake_sleep.sleeps) == 5

        # Will retry a couple of times
        fake_sleep = make_fake_sleep()

        def make_some_thing(fake_sleep):
            returns = [404, 404, 200]

            @retry(retryable_return=is_not_200, sleep_function=fake_sleep)
            def some_thing():
                return returns.pop(0)

            return some_thing

        some_thing = make_some_thing(fake_sleep)
        some_thing()
        assert fake_sleep.sleeps == [2, 2]

        # Will succeed and not retry because the return value is fine
        fake_sleep = make_fake_sleep()

        @retry(retryable_return=is_not_200, sleep_function=fake_sleep)
        def some_thing():
            return 200

        some_thing()
        assert fake_sleep.sleeps == []

    def test_retries_correct_number_of_times(self):
        fake_sleep = make_fake_sleep()

        @retry(sleep_function=fake_sleep)
        def some_thing():
            raise Exception

        with pytest.raises(Exception):
            some_thing()

        assert fake_sleep.sleeps == [2, 2, 2, 2, 2]

    def test_wait_time_generator(self):
        def waits():
            for i in [1, 1, 2, 2, 1, 1]:
                yield i

        fake_sleep = make_fake_sleep()

        @retry(wait_time_generator=waits, sleep_function=fake_sleep)
        def some_thing():
            raise Exception

        with pytest.raises(Exception):
            some_thing()
        assert fake_sleep.sleeps == [1, 1, 2, 2, 1, 1]
