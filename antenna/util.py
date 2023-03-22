# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import datetime
from functools import wraps
import json
import logging
import re
import string
import time
import uuid

import isodate
from more_itertools import peekable


logger = logging.getLogger(__name__)


UTC = isodate.UTC


def utc_now():
    """Return a timezone aware datetime instance in UTC timezone.

    This funciton is mainly for convenience. Compare:

        >>> from antenna.util import utc_now
        >>> utc_now()
        datetime.datetime(2012, 1, 5, 16, 42, 13, 639834,
          tzinfo=<isodate.tzinfo.Utc object at 0x101475210>)

    Versus:

        >>> import datetime
        >>> from antenna.util import UTC
        >>> datetime.datetime.now(UTC)
        datetime.datetime(2012, 1, 5, 16, 42, 13, 639834,
          tzinfo=<isodate.tzinfo.Utc object at 0x101475210>)

    """
    return datetime.datetime.now(UTC)


def isoformat_to_time(data):
    """Convert an isoformat string to seconds since epoch

    :arg str data: datetime in isoformat

    :returns: time in seconds as a float (equivalent to time.time() return); or 0.0
        if it's a bad datetime

    """
    try:
        dt = datetime.datetime.fromisoformat(data)
        return dt.timestamp()
    except ValueError:
        return 0.0


def json_ordered_dumps(data):
    """Dump Python data into JSON with sorted_keys.

    This returns a str. If you need bytes, do this::

         json_ordered_dumps(data).encode('utf-8')

    :arg varies data: The data to convert to JSON

    :returns: string

    """
    return json.dumps(data, sort_keys=True)


def create_crash_id(timestamp=None, throttle_result=1):
    """Generate a crash id.

    Crash ids have the following format::

        de1bb258-cbbf-4589-a673-34f800160918
                                     ^^^^^^^
                                     ||____|
                                     |  yymmdd
                                     |
                                     throttle_result

    The ``throttle_result`` should be either 0 (accept) or 1 (defer).

    :arg date/datetime timestamp: a datetime or date to use in the crash id
    :arg int throttle_result: the throttle result to encode; defaults to 1
        which is DEFER

    :returns: crash id as str

    """
    if timestamp is None:
        timestamp = utc_now().date()

    id_ = str(uuid.uuid4())
    return "%s%d%02d%02d%02d" % (
        id_[:-7],
        throttle_result,
        timestamp.year % 100,
        timestamp.month,
        timestamp.day,
    )


CRASH_ID_RE = re.compile(
    r"""
    ^
    [a-f0-9]{8}-
    [a-f0-9]{4}-
    [a-f0-9]{4}-
    [a-f0-9]{4}-
    [a-f0-9]{6}
    [0-9]{6}      # date in YYMMDD
    $
""",
    re.VERBOSE,
)


def validate_crash_id(crash_id, strict=True):
    """Return whether this is a valid crash id.

    :arg str crash_id: the crash id in question
    :arg boolean strict: whether or not to be strict about the throttle character

    :returns: true if it's valid, false if not

    """
    # Assert the shape is correct
    if not CRASH_ID_RE.match(crash_id):
        return False

    # Check throttle character
    if strict:
        if crash_id[-7] not in ("0", "1"):
            return False

    return True


def get_throttle_from_crash_id(crash_id):
    """Retrieve the throttle instruction from the crash_id.

    :arg str crash_id: the crash id

    :returns: int

    """
    return int(crash_id[-7])


def get_date_from_crash_id(crash_id, as_datetime=False):
    """Retrieve the date from the crash id.

    :arg str crash_id: the crash id
    :arg bool as_datetime: whether or not to return a datetime; defaults to False
        which means this returns a string

    :returns: string or datetime depending on ``as_datetime`` value

    """
    s = "20" + crash_id[-6:]
    if as_datetime:
        return datetime.datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), tzinfo=UTC)
    return s


ALPHA_NUMERIC_UNDERSCORE = string.ascii_letters + string.digits + "_"


def sanitize_key_name(val):
    """Sanitize a key name.

    :param val: the value to sanitize

    :returns: the value as a sanitized str

    """
    if isinstance(val, bytes):
        val = val.decode("utf-8")

    # Dump names can only contain ASCII alpha-numeric characters and
    # underscores
    val = "".join(v for v in val if v in ALPHA_NUMERIC_UNDERSCORE)

    # Dump names can't be longer than 30 characters
    val = val[:30]

    return val


class MaxAttemptsError(Exception):
    """Maximum attempts error."""

    def __init__(self, msg, ret=None):
        super().__init__(msg)
        self.return_value = ret


def wait_time_generator():
    """Return generator for wait times."""
    yield from [2, 2, 2, 2, 2]


def retry(
    retryable_exceptions=Exception,
    retryable_return=None,
    wait_time_generator=wait_time_generator,
    sleep_function=time.sleep,
    module_logger=None,
):
    """Retry decorated function with wait times, max attempts, and logging.

    Example with defaults::

        @retry()
        def some_thing_that_fails():
            pass


    Example with arguments::

        import logging
        logger = logging.getLogger(__name__)

        @retry(
            retryable_exceptions=[SocketTimeout, ConnectionError],
            retryable_return=lambda resp: resp.status_code != 200,
            module_logger=logger
        )
        def some_thing_that_does_connections():
            pass


    :arg exception/list retryable_exceptions:
        Exception class or list of exception classes to catch and retry on.

        Any exceptions not in this list will bubble up.

        Defaults to ``Exception``.

    :arg fun retryable_return:
        A function that takes a function return and returns ``True`` to retry
        or ``False`` to stop retrying.

        This allows you to retry based on a failed exception or failed return.

    :arg wait_time_generator:
        Generator function that returns wait times until a maximum number of
        attempts have been tried.

    :arg fun sleep_function:
        Function that takes the current attempt number as an int and sleeps.

    :arg logger/None module_logger:
        If you want to log all the exceptions that are caught and retried,
        then provide a logger.

        Otherwise exceptions are silently ignored.

    :raises MaxAttemptsError: if the maximum number of attempts have occurred.
        If the error is an exception, then the actual exception is part of
        the exception chain. If the error is a return value, then the
        problematic return value is in ``return_value``.

    """
    if not isinstance(retryable_exceptions, type):
        retryable_exceptions = tuple(retryable_exceptions)

    if module_logger is not None:
        log_warning = module_logger.warning
    else:
        log_warning = lambda *args, **kwargs: None  # noqa

    def _retry_inner(fun):
        @wraps(fun)
        def _retry_fun(*args, **kwargs):
            attempts = 0
            wait_times = peekable(wait_time_generator())
            while True:
                try:
                    ret = fun(*args, **kwargs)
                    if retryable_return is None or not retryable_return(ret):
                        # This was a successful return--yay!
                        return ret

                    # The return value is "bad", so we log something and then
                    # do another iteration.
                    log_warning(
                        "%s: bad return, retry attempt %s",
                        fun.__qualname__,
                        attempts,
                    )

                    # If last attempt,
                    if not wait_times:
                        raise MaxAttemptsError(
                            "Maximum retry attempts; last return %r." % ret, ret
                        )

                except retryable_exceptions as exc:
                    # If it's a MaxAttemptsError, re-raise that
                    if isinstance(exc, MaxAttemptsError):
                        raise

                    # Retryable exception is thrown, so we log something and then do
                    # another iteration
                    log_warning(
                        "%s: exception %s, retry attempt %s",
                        fun.__qualname__,
                        exc,
                        attempts,
                    )

                    # If last attempt, raise MaxAttemptsError which will chain the
                    # current errror
                    if not wait_times:
                        raise MaxAttemptsError(
                            f"Maximum retry attempts: {exc!r}"
                        ) from exc

                sleep_function(next(wait_times))
                attempts += 1

        return _retry_fun

    return _retry_inner
