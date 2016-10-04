# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import gzip
import io
import json


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
