# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging


logger = logging.getLogger(__name__)


class CrashStorageBase:
    """Crash storage base class"""
    def __init__(self, config):
        pass

    def save_raw_crash(self, raw_crash, dumps, crash_id):
        """Saves the raw crash and related dumps"""
        raise NotImplementedError


class NoOpCrashStorage(CrashStorageBase):
    """This is a no-op crash storage that logs crashes it would have stored

    It keeps track of the last 10 crashes in ``.crashes`` with the most
    recently stored crash at the end of the list.

    """
    def __init__(self, config):
        super().__init__(config)
        self.crashes = []

    def add_crash(self, raw_crash, dumps, crash_id):
        self.crashes.append(
            (raw_crash, dumps, crash_id)
        )
        # Nix all but the last 10 crashes
        self.crashes = self.crashes[-10:]

    def save_raw_crash(self, raw_crash, dumps, crash_id):
        logger.info('crash no-op: %s %s %s', crash_id, raw_crash, dumps.keys())
        self.add_crash(raw_crash, dumps, crash_id)
