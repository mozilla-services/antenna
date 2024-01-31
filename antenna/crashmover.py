# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
import logging

from everett.manager import Option, parse_class
import markus

from antenna.util import MaxAttemptsError, retry


LOGGER = logging.getLogger(__name__)
MYMETRICS = markus.get_metrics("crashmover")


#: Maximum number of attempts to save or publish a crash before we give up
MAX_ATTEMPTS = 5

#: Seconds to sleep between attempts to save or publish a crash
RETRY_SLEEP_SECONDS = 2


def _incr_wait_generator(
    counter, attempts=MAX_ATTEMPTS, sleep_seconds=RETRY_SLEEP_SECONDS
):
    def _generator_generator():
        for _ in range(attempts - 1):
            MYMETRICS.incr(counter)
            yield sleep_seconds

    return _generator_generator


@dataclass
class CrashReport:
    """Crash report structure."""

    raw_crash: dict
    dumps: dict[str, bytes]
    crash_id: str


class CrashMover:
    """Handles saving and publishing crash reports.

    The crashmover saves the crash using the configured crashstorage class and
    publishes it using the configured crashpublish class.

    .. Note::

       From when a crash comes in to when it's saved by the crashstorage class, the
       crash is entirely in memory. Keep that in mind when figuring out how to scale
       your Antenna nodes.


    The most important configuration bit here is choosing the crashstorage class.

    For example::

        CRASHMOVER_CRASHSTORAGE_CLASS=antenna.ext.s3.crashstorage.S3CrashStorage


    """

    class Config:
        # crashstorage class for saving crash data
        crashstorage_class = Option(
            default="antenna.ext.crashstorage_base.NoOpCrashStorage",
            parser=parse_class,
            doc="The class in charge of storing crashes.",
        )

        # crashpublish class for publishing crash ids for processing
        crashpublish_class = Option(
            default="antenna.ext.crashpublish_base.NoOpCrashPublish",
            parser=parse_class,
            doc="The class in charge of publishing crashes.",
        )

    def __init__(self, config):
        self.config = config.with_options(self)

        self.crashstorage = self.config("crashstorage_class")(
            config.with_namespace("crashstorage")
        )
        self.crashpublish = self.config("crashpublish_class")(
            config.with_namespace("crashpublish")
        )

    def get_components(self):
        """Return map of namespace -> component for traversing component tree."""
        return {
            "crashstorage": self.crashstorage,
            "crashpublish": self.crashpublish,
        }

    def check_health(self, state):
        """Return health state."""
        if hasattr(self.crashstorage, "check_health"):
            self.crashstorage.check_health(state)
        if hasattr(self.crashpublish, "check_health"):
            self.crashpublish.check_health(state)

    @MYMETRICS.timer("crash_handling.time")
    def handle_crashreport(self, raw_crash, dumps, crash_id):
        """Handle a new crash report synchronously and return whether that succeeded.

        :arg raw_crash: map of key/val crash annotations
        :arg dumps: map of name to memory dump
        :arg crash_id: the crash id for the crash report

        :returns: True if the crash report was saved, regardless of whether the crash
            id was published for processing.
        """

        crash_report = CrashReport(raw_crash, dumps, crash_id)

        try:
            self.crashmover_save(crash_report)
        except MaxAttemptsError:
            # After max attempts, we give up on this crash
            LOGGER.error(f"{crash_id}: too many errors trying to save; dropped")
            MYMETRICS.incr("save_crash_dropped.count")
            return False

        try:
            self.crashmover_publish(crash_report)
            MYMETRICS.incr("save_crash.count")
        except MaxAttemptsError:
            LOGGER.error(f"{crash_id}: too many errors trying to publish; dropped")
            MYMETRICS.incr("publish_crash_dropped.count")
            # return True even when publish fails because it will be automatically
            # published later via self-healing mechanisms

        return True

    @retry(
        module_logger=LOGGER,
        wait_time_generator=_incr_wait_generator("save_crash_exception.count"),
    )
    @MYMETRICS.timer("crash_save.time")
    def crashmover_save(self, crash_report):
        """Save crash report to storage."""
        self.crashstorage.save_crash(crash_report)
        LOGGER.info("%s saved", crash_report.crash_id)

    @retry(
        module_logger=LOGGER,
        wait_time_generator=_incr_wait_generator("publish_crash_exception.count"),
    )
    @MYMETRICS.timer("crash_publish.time")
    def crashmover_publish(self, crash_report):
        """Publish crash_id in publish queue."""
        self.crashpublish.publish_crash(crash_report)
        LOGGER.info("%s published", crash_report.crash_id)
