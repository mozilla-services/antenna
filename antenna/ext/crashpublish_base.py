# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

from everett.component import ConfigOptions, RequiredConfigMixin


logger = logging.getLogger(__name__)


class CrashPublishBase(RequiredConfigMixin):
    """Crash publishstorage base class."""

    required_config = ConfigOptions()

    def __init__(self, config):
        self.config = config.with_options(self)

    def publish_crash(self, crash_id):
        """Publish the crash id

        FIXME(willkg): How should this method handle exceptions?

        :arg str crash_id: The crash id as a string.

        """
        raise NotImplementedError


class NoOpCrashPublish(CrashPublishBase):
    """This is a no-op crash publish class that logs crashes it would have published.

    It keeps track of the last 10 crash ids in ``.crashes`` instance attribute
    with the most recently published crash id at the end of the list. This
    helps when writing unit tests for Antenna.

    """

    def __init__(self, config):
        super().__init__(config)
        self.published_things = []

    def add_published_thing(self, crash_id):
        self.published_things.append({
            'crash_id': crash_id,
        })
        # Nix all but the last 10 crashes
        self.published_things = self.published_things[-10:]

    def publish_crash(self, crash_id):
        logger.info(
            'crash publish no-op: %s',
            crash_id,
        )
        self.add_published_thing(crash_id)
