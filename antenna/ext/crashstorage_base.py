# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging

from everett.component import ConfigOptions, RequiredConfigMixin


logger = logging.getLogger(__name__)


class CrashStorageBase(RequiredConfigMixin):
    """Crash storage base class."""

    required_config = ConfigOptions()

    def __init__(self, config):
        self.config = config.with_options(self)

    def publish_crash(self, crash_report):
        """Save the crash report."""
        raise NotImplementedError


class NoOpCrashStorage(CrashStorageBase):
    """This is a no-op crash storage that logs crashes it would have stored.

    It keeps track of the last 10 crashes in ``.saved_things`` instance
    attribute with the most recently stored crash at the end of the list. This
    helps when writing unit tests for Antenna.

    """

    def __init__(self, config):
        super().__init__(config)
        self.saved_things = []

    def save_crash(self, crash_report):
        """Save a raw crash."""
        crash_id = crash_report.crash_id
        logger.info("crash storage no-op: %s", crash_id)
        self.saved_things.append({"crash_id": crash_id})

        # Nix all but the last 10 crashes
        self.saved_things = self.saved_things[-10:]
