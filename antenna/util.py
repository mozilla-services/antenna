# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


def de_null(value):
    """Remove nulls from bytes and str values"""
    if isinstance(value, bytes) and b'\0' in value:
        # FIXME: might need to use translate(None, b'\0')
        return value.replace(b'\0', b'')
    if isinstance(value, str) and '\0' in value:
        return value.replace('\0', '')
    return value
