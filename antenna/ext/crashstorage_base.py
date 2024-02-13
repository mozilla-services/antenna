# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging

from antenna.util import get_date_from_crash_id


logger = logging.getLogger(__name__)


class CrashStorageBase:
    """Crash storage base class."""

    class Config:
        pass

    def __init__(self, config):
        self.config = config.with_options(self)

    def _path_join(self, *paths):
        return "/".join(paths)

    def _get_raw_crash_path(self, crash_id):
        date = get_date_from_crash_id(crash_id)
        return self._path_join("v1", "raw_crash", date, crash_id)

    def _get_dump_names_path(self, crash_id):
        return self._path_join("v1", "dump_names", crash_id)

    def _get_dump_name_path(self, crash_id, dump_name):
        # NOTE(willkg): This is something that Socorro collector did. I'm not
        # really sure why, but in order to maintain backwards compatability, we
        # need to keep doing it.
        if dump_name in (None, "", "upload_file_minidump"):
            dump_name = "dump"

        return self._path_join("v1", dump_name, crash_id)

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
