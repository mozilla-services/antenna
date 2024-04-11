# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging


logger = logging.getLogger(__name__)


class CrashIDNotFound(Exception):
    pass


class CrashStorageBase:
    """Crash storage base class."""

    class Config:
        pass

    def __init__(self, config):
        self.config = config.with_options(self)

    def save_crash(self, crash_report):
        """Save the crash report

        :arg crash_report: the CrashReport instance

        """
        raise NotImplementedError

    def load_crash(self, crash_id):
        """Load crash report data by crash id.

        :arg crash_id: the crash id to retrieve data for

        :returns: CrashReport instance

        :raises CrashIDNotFound: if crash report data doesn't exist

        """
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
        crash_id = crash_report.crash_id
        logger.info("crash storage no-op: %s", crash_id)
        self.saved_things.append(crash_report)

        # Nix all but the last 10 crashes
        self.saved_things = self.saved_things[-10:]

    def load_crash(self, crash_id):
        for crash_report in self.saved_things:
            if crash_report.crash_id == crash_id:
                return crash_report

        raise CrashIDNotFound(f"no data for {crash_id}")
