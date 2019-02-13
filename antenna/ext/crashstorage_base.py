# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

from everett.component import ConfigOptions, RequiredConfigMixin


logger = logging.getLogger(__name__)


class CrashStorageBase(RequiredConfigMixin):
    """Crash storage base class."""

    required_config = ConfigOptions()

    def __init__(self, config):
        self.config = config.with_options(self)

    def save_raw_crash(self, crash_id, raw_crash, dumps):
        """Save the raw crash and related dumps.

        FIXME(willkg): How should this method handle exceptions?

        :arg str crash_id: The crash id as a string.
        :arg dict raw_crash: dict The raw crash as a dict.

        """
        raise NotImplementedError

    def save_dumps(self, crash_id, dumps):
        """Save dump data.

        :arg str crash_id: The crash id
        :arg dict dumps: dump name -> dump

        """
        raise NotImplementedError

    def load_raw_crash(self, crash_id):
        """Load and thaw out a raw crash.

        :arg str crash_id: crash id of the crash as a string

        :returns: tuple of (raw_crash dict, dumps dict)

        """
        raise NotImplementedError


class NoOpCrashStorage(CrashStorageBase):
    """This is a no-op crash storage that logs crashes it would have stored.

    It keeps track of the last 10 crashes in ``.crashes`` instance attribute
    with the most recently stored crash at the end of the list. This helps
    when writing unit tests for Antenna.

    """

    def __init__(self, config):
        super().__init__(config)
        self.saved_things = []

    def _add_saved_thing(self, crash_id, type_, data):
        self.saved_things.append({
            'crash_id': crash_id,
            'type': type_,
            'data': data
        })
        # Nix all but the last 10 crashes
        self.saved_things = self.saved_things[-10:]

    def _truncate_raw_crash(self, raw_crash):
        """Truncate a raw crash to something printable in a log."""
        return sorted(raw_crash.items())[:10]

    def _truncate_dumps(self, dumps):
        """Truncate dumps information to something printable to a log."""
        return sorted(dumps.keys())

    def save_raw_crash(self, crash_id, raw_crash):
        """Save a raw crash."""
        logger.info(
            'crash storage no-op: %s raw_crash %s',
            crash_id,
            self._truncate_raw_crash(raw_crash),
        )
        self._add_saved_thing(crash_id, 'raw_crash', raw_crash)

    def save_dumps(self, crash_id, dumps):
        """Save a crash dump."""
        for name, data in dumps.items():
            logger.info(
                'crash storage no-op: %s dump %s (%d)',
                crash_id,
                name,
                len(data)
            )
            self._add_saved_thing(crash_id, name, data)
