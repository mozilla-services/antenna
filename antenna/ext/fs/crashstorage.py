# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging
import os
import os.path

from everett.manager import Option

from antenna.ext.crashstorage_base import CrashStorageBase
from antenna.util import get_date_from_crash_id, json_ordered_dumps


logger = logging.getLogger(__name__)


class FSCrashStorage(CrashStorageBase):
    """Save raw crash files to the file system.

    This generates a tree something like this which mirrors what we do
    on S3:

    ::

        <FS_ROOT>/
            <YYYYMMDD>/
                raw_crash/
                    <CRASHID>.json
                dump_names/
                    <CRASHID>.json
                <DUMP_NAME>/
                    <CRASHID>


    Couple of things to note:

    1. This doesn't ever delete anything from the tree. You should run another
       process to clean things up.

    2. If you run out of disk space, this component will fail miserably.
       There's no way to recover from a full disk--you will lose crashes.

    FIXME(willkg): Can we alleviate or reduce the likelihood of the above?

    """

    class Config:
        fs_root = Option(
            default="/tmp/antenna_crashes",  # noqa: S108
            doc="path to where files should be stored",
        )

    # FIXME(willkg): umask

    def __init__(self, config):
        self.config = config.with_options(self)

        self.root = os.path.abspath(self.config("fs_root")).rstrip(os.sep)

        # FIXME(willkg): We should probably do more to validate fs_root. Can we
        # write files to it?
        if not os.path.isdir(self.root):
            os.makedirs(self.root)

    def _get_raw_crash_path(self, crash_id):
        """Return path for where the raw crash should go."""
        return os.path.join(
            self.root, get_date_from_crash_id(crash_id), "raw_crash", crash_id + ".json"
        )

    def _get_dump_names_path(self, crash_id):
        """Return path for where the dump_names list should go."""
        return os.path.join(
            self.root,
            get_date_from_crash_id(crash_id),
            "dump_names",
            crash_id + ".json",
        )

    def _get_dump_name_path(self, crash_id, dump_name):
        """Return path for a given dump."""
        return os.path.join(
            self.root, get_date_from_crash_id(crash_id), dump_name, crash_id
        )

    def _save_file(self, fn, contents):
        logger.debug("Saving file %r", fn)
        path = os.path.dirname(fn)

        # FIXME(willkg): What happens if there is something here already and
        # it's not a directory?
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError:
                logger.exception("Threw exception while trying to make path %r", path)
                # FIXME(willkg): If we ever make this production-ready, we
                # need a better option here.
                return

        # FIXME(willkg): This will stomp on existing crashes. Is that ok?
        # Should we detect and do something different somehow?
        with open(fn, "wb") as fp:
            fp.write(contents)

    def save_raw_crash(self, crash_id, raw_crash):
        """Save the raw crash and related dumps.

        FIXME(willkg): How should this method handle exceptions?

        :arg str crash_id: The crash id as a string.
        :arg dict raw_crash: dict The raw crash as a dict.

        """
        self._save_file(
            self._get_raw_crash_path(crash_id),
            json_ordered_dumps(raw_crash).encode("utf-8"),
        )

    def save_dumps(self, crash_id, dumps):
        """Save dump data.

        :arg str crash_id: The crash id
        :arg dict dumps: dump name -> dump

        """
        files = {}

        # Add dump_names to the list of files to save. We always generate this
        # even if there are no dumps.
        files[self._get_dump_names_path(crash_id)] = json_ordered_dumps(
            list(sorted(dumps.keys()))
        ).encode("utf-8")

        # Add the dump files if there are any.
        for dump_name, dump in dumps.items():
            files[self._get_dump_name_path(crash_id, dump_name)] = dump

        for fn, contents in files.items():
            self._save_file(fn, contents)

    def save_crash(self, crash_report):
        """Save crash data."""
        crash_id = crash_report.crash_id
        raw_crash = crash_report.raw_crash
        dumps = crash_report.dumps

        # Save dumps first
        self.save_dumps(crash_id, dumps)

        # Save raw crash
        self.save_raw_crash(crash_id, raw_crash)
