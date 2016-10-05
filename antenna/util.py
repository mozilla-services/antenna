# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import datetime
import gzip
import io
import json
import uuid

from antenna.datetimeutil import utc_now, UTC


# NOTE(willkg): This is a hold-over from Socorro. I'm not really sure what the
# depth does or whether we still need it.
DEFAULT_DEPTH = 2


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


def create_crash_id(timestamp=None):
    """Generates a crash id

    :arg timestamp: a datetime or date to use in the crash id

    :returns: crash id as str

    """
    if timestamp is None:
        timestamp = utc_now().date()
    depth = DEFAULT_DEPTH
    id_ = str(uuid.uuid4())
    return "%s%d%02d%02d%02d" % (
        id_[:-7], depth, timestamp.year % 100, timestamp.month, timestamp.day
    )


def get_date_from_crash_id(crash_id, as_datetime=False):
    """Retrieves the date from the crash id

    :arg crash_id: the crash id as a str
    :arg as_datetime: whether or not to return a datetime; defaults to False
        which means this returns a string

    :returns: string or datetime depending on ``as_datetime`` value

    """
    s = '20' + crash_id[-6:]
    if as_datetime:
        return datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), tzinfo=UTC)
    return s
