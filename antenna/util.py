# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
from functools import wraps
import gzip
import io
import json
import time
import uuid

import isodate


UTC = isodate.UTC


def utc_now():
    """Return a timezone aware datetime instance in UTC timezone

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


def de_null(value):
    """Remove nulls from bytes and str values

    :arg value: The str or bytes to remove nulls from

    :returns: str or bytes without nulls

    """
    if isinstance(value, bytes) and b'\0' in value:
        # FIXME: might need to use translate(None, b'\0')
        return value.replace(b'\0', b'')
    if isinstance(value, str) and '\0' in value:
        return value.replace('\0', '')
    return value


def json_ordered_dumps(data):
    """Dumps Python data into JSON with sorted_keys

    This returns a str. If you need bytes, do this::

         json_ordered_dumps(data).encode('utf-8')

    :arg data: The data to convert to JSON

    :returns: string

    """
    return json.dumps(data, sort_keys=True)


def compress(multipart):
    """Takes a multi-part/form-data payload and compresses it

    :arg multipart: a bytes object representing a multi-part/form-data

    :returns: bytes compressed

    """
    bio = io.BytesIO()
    g = gzip.GzipFile(fileobj=bio, mode='w')
    g.write(multipart)
    g.close()
    return bio.getbuffer()


def create_crash_id(timestamp=None, throttle_result=1):
    """Generates a crash id

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
        id_[:-7], throttle_result, timestamp.year % 100, timestamp.month, timestamp.day
    )


def get_throttle_from_crash_id(crash_id):
    """Retrieve the throttle instruction from the crash_id

    :arg str crash_id: the crash id

    :returns: int

    """
    return int(crash_id[-7])


def get_date_from_crash_id(crash_id, as_datetime=False):
    """Retrieves the date from the crash id

    :arg str crash_id: the crash id
    :arg bool as_datetime: whether or not to return a datetime; defaults to False
        which means this returns a string

    :returns: string or datetime depending on ``as_datetime`` value

    """
    s = '20' + crash_id[-6:]
    if as_datetime:
        return datetime.datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), tzinfo=UTC)
    return s


class MaxAttemptsError(Exception):
    """Maximum attempts error.

    .. :py:attribute:: msg
       message for the exception

    .. :py:attribute:: return_value
       The last return value for the function.

    """
    def __init__(self, msg, ret):
        super().__init__(msg)
        self.return_value = ret


# Tuple of retry times in seconds in order of attempt.
RETRY_TIMES = (
    1,
    5,
    10,
    30,
    60,
    2 * 60,
)
RETRY_TIMES_MAX_INDEX = len(RETRY_TIMES) - 1


def retry(retryable_exceptions=Exception, retryable_return=None, max_attempts=10,
          sleep_function=time.sleep, module_logger=None):
    """Decorator for retrying with exponential wait and logging

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

    :arg int/None max_attempts:
        The maximum number of times this will retry. After max attempts, it'll
        reraise the last exception in the case of an exception or raise a
        ``MaxAttemptsError`` in the case of invalid return values.

        If ``max_attempts`` is ``None``, this will try indefinitely.

    :arg fun sleep_function:
        Function that takes the current attempt number as an int and sleeps.

    :arg logger/None module_logger:
        If you want to log all the exceptions that are caught and retried,
        then provide a logger.

        Otherwise exceptions are silently ignored.

    """
    if not isinstance(retryable_exceptions, type):
        retryable_exceptions = tuple(retryable_exceptions)

    def _retry_inner(fun):
        @wraps(fun)
        def _retry_fun(*args, **kwargs):
            attempts = 0
            while True:
                try:
                    ret = fun(*args, **kwargs)
                    if retryable_return is None or not retryable_return(ret):
                        return ret

                    elif max_attempts is not None and attempts >= max_attempts:
                        raise MaxAttemptsError(
                            'Maximum retry attempts. Error return.', ret
                        )

                except retryable_exceptions:
                    if module_logger is not None:
                        module_logger.exception('retry attempt %s', attempts)

                    if max_attempts is not None and attempts >= max_attempts:
                        raise

                sleep_function(RETRY_TIMES[min(attempts, RETRY_TIMES_MAX_INDEX)])
                attempts += 1

        return _retry_fun
    return _retry_inner
