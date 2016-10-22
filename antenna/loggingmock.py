# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""This module holds logging mock to make it easier to test Antenna.

Putting this in a separate file in case I want to lift it.

"""

import logging


class LoggingMock(logging.Handler):
    def __init__(self, names=None):
        super().__init__(level=1)
        self.names = names
        self.records = []

    def filter(self, record):
        return True

    def emit(self, record):
        self.records.append(record)

    def install_handler(self):
        if self.names is None:
            self.names = [None]

        for name in self.names:
            logger = logging.getLogger(name)
            logger.addHandler(self)

    def uninstall_handler(self):
        for name in self.names:
            logger = logging.getLogger(name)
            logger.removeHandler(self)

    def __enter__(self):
        self.records = []
        self.install_handler()
        return self

    def has_record(self, name=None, levelname=None, msg_contains=None):
        if isinstance(msg_contains, str):
            msg_contains = [msg_contains]

        def match_name(record_name):
            return name is None or name == record_name

        def match_levelname(record_levelname):
            return levelname is None or levelname == record_levelname

        def match_message(record_msg):
            if msg_contains is None:
                return True
            for part in msg_contains:
                if part not in record_msg:
                    return False

            return True

        for record in self.records:
            if (
                    match_name(record.name) and
                    match_levelname(record.levelname) and
                    match_message(record.message)
            ):
                return True

        return False

    def get_records(self):
        return self.records

    def print_records(self):
        records = self.get_records()
        if records:
            for record in records:
                print((record.name, record.levelname, record.message))
        else:
            print('NO RECORDS')

    def clear(self):
        self.records = []

    def __exit__(self, exc_type, exc_value, traceback):
        self.uninstall_handler()
