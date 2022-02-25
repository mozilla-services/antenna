# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Module holding Sentry-related functions.

Infrastructure for optionally wrapping things in Sentry contexts to capture
unhandled exceptions.
"""

import logging

import sentry_sdk
from sentry_sdk.integrations.falcon import FalconIntegration

from antenna.util import get_version_info


LOGGER = logging.getLogger(__name__)


def get_release(basedir):
    version_info = get_version_info(basedir)

    version = version_info.get("version", "none")

    commit = version_info.get("commit")
    commit = commit[:8] if commit else "unknown"

    return f"{version}:{commit}"


def setup_sentry(basedir, host_id, sentry_dsn):
    """Setup Sentry with Falcon

    https://docs.sentry.io/platforms/python/guides/falcon/

    """
    if not sentry_dsn:
        return

    release = get_release(basedir)

    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[FalconIntegration()],
        send_default_pii=False,
        release=release,
        server_name=host_id,
    )
    LOGGER.info("set up sentry")
