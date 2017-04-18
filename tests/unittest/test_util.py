# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import datetime
import sys

from freezegun import freeze_time
import pytest

from antenna.util import (
    MaxAttemptsError,
    create_crash_id,
    de_null,
    get_date_from_crash_id,
    get_throttle_from_crash_id,
    get_version_info,
    one_line_exception,
    retry,
    utc_now,
)


def test_utc_now():
    res = utc_now()
    assert res.strftime('%Z') == 'UTC'
    assert res.strftime('%z') == '+0000'
    assert res.tzinfo


def test_get_version_info(tmpdir):
    fn = tmpdir.join('/version.json')
    fn.write_text('{"commit": "d6ac5a5d2acf99751b91b2a3ca651d99af6b9db3"}', encoding='utf-8')

    assert (
        get_version_info(str(tmpdir)) ==
        {'commit': 'd6ac5a5d2acf99751b91b2a3ca651d99af6b9db3'}
    )


@pytest.mark.parametrize('data,expected', [
    # no nulls--just making sure things are good
    ('abc', 'abc'),
    (b'abc', b'abc'),
    (123, 123),

    # has nulls
    ('abc\u0000', 'abc'),
    ('abc\0', 'abc'),
    ('ab\0c\0', 'abc'),
    (b'abc\0', b'abc'),
    (b'a\0bc\0', b'abc'),
])
def test_de_null(data, expected):
    assert de_null(data) == expected


@freeze_time('2011-09-06 00:00:00', tz_offset=0)
def test_crash_id():
    """Tests creating crash ids"""
    crash_id = create_crash_id()

    assert get_date_from_crash_id(crash_id) == '20110906'
    assert get_date_from_crash_id(crash_id, as_datetime=True).strftime('%Y%m%d') == '20110906'

    # Defaults to 1
    assert get_throttle_from_crash_id(crash_id) == 1


def test_crash_id_with_throttle():
    crash_id = create_crash_id(throttle_result=0)

    assert get_throttle_from_crash_id(crash_id) == 0


def test_crash_id_with_date():
    """Tests creating a crash id with a timestamp"""
    crash_id = create_crash_id(datetime(2016, 10, 4))

    assert get_date_from_crash_id(crash_id) == '20161004'


class Test_retry:
    """Tests for the retry decorator"""
    def test_retry(self):
        """Test that retry doesn't affect function return"""
        @retry()
        def some_thing():
            return 1

        assert some_thing() == 1

    def test_retry_retryable_exceptions(self):
        """Test retry retryable_exceptions arg does the right thing"""
        sleeps = []

        def fake_sleep(attempt):
            sleeps.append(attempt)

        # This will fail on the first attempt because Exception is not
        # in the list of retryable exceptions.
        @retry(retryable_exceptions=ValueError, sleep_function=fake_sleep)
        def some_thing():
            raise Exception

        with pytest.raises(Exception):
            some_thing()
        assert len(sleeps) == 0

        sleeps = []

        # This will fail on the first attempt because Exception is not
        # in the list of retryable exceptions.
        @retry(retryable_exceptions=[ValueError, IndexError], sleep_function=fake_sleep)
        def some_thing():
            raise Exception

        with pytest.raises(Exception):
            some_thing()
        assert len(sleeps) == 0

        sleeps = []

        # This will retry until the max attempts and then reraise the exception
        @retry(retryable_exceptions=ValueError, sleep_function=fake_sleep)
        def some_thing():
            raise ValueError

        with pytest.raises(ValueError):
            some_thing()
        assert len(sleeps) == 5

    def test_retry_retryable_return(self):
        """Tests retry retryable_return arg does the right thing"""
        sleeps = []

        def fake_sleep(attempt):
            sleeps.append(attempt)

        def is_not_200(ret):
            return ret != 200

        # Will keep retrying until max_attempts and then raise an error that includes
        # the last function return
        @retry(retryable_return=is_not_200, sleep_function=fake_sleep)
        def some_thing():
            return 404

        with pytest.raises(MaxAttemptsError) as excinfo:
            some_thing()

        assert excinfo.value.return_value == 404
        assert len(sleeps) == 5

        sleeps = []

        # Will succeed and not retry because the return value is fine
        @retry(retryable_return=is_not_200, sleep_function=fake_sleep)
        def some_thing():
            return 200

        some_thing()
        assert len(sleeps) == 0

    def test_retry_amounts(self):
        sleeps = []

        def fake_sleep(attempt):
            sleeps.append(attempt)

        @retry(sleep_function=fake_sleep)
        def some_thing():
            raise Exception

        with pytest.raises(Exception):
            some_thing()

        assert sleeps == [1, 1, 5, 10, 30]

    def test_wait_time_generator(self):
        sleeps = []

        def fake_sleep(attempt):
            sleeps.append(attempt)

        @retry(sleep_function=fake_sleep)
        def some_thing():
            raise Exception

        with pytest.raises(Exception):
            some_thing()
        assert len(sleeps) == 5

        sleeps = []

        def waits():
            for i in [1, 1, 2, 2, 1, 1]:
                yield i

        @retry(wait_time_generator=waits, sleep_function=fake_sleep)
        def some_thing():
            raise Exception

        with pytest.raises(Exception):
            some_thing()
        assert sleeps == [1, 1, 2, 2, 1, 1]


def test_one_line_exception():
    try:
        1 / 0

    except ZeroDivisionError:
        exc_no_args = one_line_exception()
        exc_args = one_line_exception(sys.exc_info())

    assert '\n' not in exc_no_args
    assert '\n' not in exc_args
    assert exc_no_args == exc_args

    assert exc_args.endswith('ZeroDivisionError: division by zero')
