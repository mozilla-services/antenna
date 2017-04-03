# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
from functools import wraps
import json
import logging
from pathlib import Path
import sys
import time
import traceback
import uuid

import isodate


logger = logging.getLogger(__name__)


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


def get_version_info(basedir):
    """Given a basedir, retrieves version information for this deploy

    :arg str basedir: the path of the base directory where ``version.json``
        exists

    :returns: version info as a dict or an empty dict

    """
    try:
        path = Path(basedir) / 'version.json'
        with open(str(path), 'r') as fp:
            commit_info = json.loads(fp.read().strip())
    except (IOError, OSError):
        logger.error('Exception thrown when retrieving version.json', exc_info=True)
        commit_info = {}
    return commit_info


def de_null(value):
    """Remove nulls from bytes and str values

    :arg str/bytes value: The str or bytes to remove nulls from

    :returns: str or bytes without nulls

    """
    if isinstance(value, bytes) and b'\0' in value:
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


def wait_time_generator():
    for amt in [1, 1, 5, 10, 30]:
        yield amt


def retry(retryable_exceptions=Exception,
          retryable_return=None,
          wait_time_generator=wait_time_generator,
          sleep_function=time.sleep,
          module_logger=None):
    """Decorator for retrying with wait times, max attempts and logging

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

    """
    if not isinstance(retryable_exceptions, type):
        retryable_exceptions = tuple(retryable_exceptions)

    def _retry_inner(fun):
        @wraps(fun)
        def _retry_fun(*args, **kwargs):
            attempts = 0
            wait_times = wait_time_generator()

            while True:
                # Grab the next wait time and if there isn't one, then this is
                # the last attempt
                try:
                    next_wait = next(wait_times)
                except StopIteration:
                    next_wait = None

                try:
                    ret = fun(*args, **kwargs)
                    if retryable_return is None or not retryable_return(ret):
                        # This was a successful return--yay!
                        return ret

                    # The return value is "bad", so we log something and then
                    # do another iteration.
                    if module_logger is not None:
                        module_logger.warning(
                            '%s: bad return, retry attempt %s',
                            fun.__qualname__,
                            attempts
                        )

                    # If last attempt, then raise MaxAttemptsError
                    if next_wait is None:
                        raise MaxAttemptsError('Maximum retry attempts.', ret)

                except retryable_exceptions as exc:
                    # Retryable exception is thrown, so we log something and
                    # then do another iteration.
                    if module_logger is not None:
                        module_logger.warning(
                            '%s: exception %s, retry attempt %s',
                            fun.__qualname__,
                            exc,
                            attempts
                        )

                    # If last attempt, re-raise the exception thrown
                    if next_wait is None:
                        raise

                sleep_function(next_wait)
                attempts += 1

        return _retry_fun
    return _retry_inner


def one_line_exception(exc_info=None):
    """Formats an exception such that it's all on one line

    This fixes some problems with interleaved logging, but it's annoying. To
    convert the line back do this::

        line.replace('<NL>', '\n')

    """
    if exc_info is None:
        exc_info = sys.exc_info()

    return ''.join(traceback.format_exception(*exc_info)).strip().replace('\n', '<NL>')
