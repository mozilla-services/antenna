# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from collections import deque
import logging
import time

from everett.manager import Option, parse_class
from gevent.pool import Pool
import markus

from antenna.heartbeat import register_for_life, register_for_heartbeat
from antenna.util import isoformat_to_time


LOGGER = logging.getLogger(__name__)
MYMETRICS = markus.get_metrics("crashmover")


#: Maximum number of attempts to save a crash before we give up
MAX_ATTEMPTS = 20

#: SAVE and PUBLISH states of the crash mover
STATE_SAVE = "save"
STATE_PUBLISH = "publish"


# FIXME: convert this to a dataclass
class CrashReport:
    """Crash report structure."""

    def __init__(self, raw_crash, dumps, crash_id, errors=0):
        self.raw_crash = raw_crash
        self.dumps = dumps
        self.crash_id = crash_id
        self.errors = errors

        self.state = None

    def set_state(self, state):
        """Set new state and reset errors."""
        self.state = state
        self.errors = 0


def positive_int(val):
    """Everett parser that enforces val >= 1."""
    val = int(val)
    if val < 1:
        raise ValueError("val must be greater than 1: %s" % val)
    return val


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
        concurrent_crashmovers = Option(
            default="2",
            parser=positive_int,
            doc=(
                "The number of crashes concurrently being saved and published. "
                "Each process gets this many concurrent crashmovers, so if you're "
                "running 5 processes on the node, then it's "
                "(5 * concurrent_crashmovers) sharing upload bandwidth."
            ),
        )

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

        # Gevent pool for crashmover workers
        self.crashmover_pool = Pool(size=self.config("concurrent_crashmovers"))

        # Queue for crashmover work
        self.crashmover_queue = deque()

        # Register hb functions with heartbeat manager
        register_for_heartbeat(self.hb_report_health_stats)
        register_for_heartbeat(self.hb_run_crashmover)

        # Register life function with heartbeat manager
        register_for_life(self.has_work_to_do)

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

    def hb_report_health_stats(self):
        """Heartbeat function to report health stats."""
        # The number of crash reports sitting in the work queue; this is a
        # direct measure of the health of this process--a number that's going
        # up means impending doom
        MYMETRICS.gauge("work_queue_size", value=len(self.crashmover_queue))

    def has_work_to_do(self):
        """Return whether this still has work to do."""
        work_to_do = len(self.crashmover_pool) + len(self.crashmover_queue)
        LOGGER.info("work left to do: %s" % work_to_do)
        # Indicates whether or not we're sitting on crashes to save--this helps
        # keep Antenna alive until we're done saving crashes
        return bool(work_to_do)

    def hb_run_crashmover(self):
        """Spawn a crashmover if there's work to do."""
        # Spawn a new crashmover if there's stuff in the queue and we haven't
        # hit the limit of how many we can run
        if self.crashmover_queue and self.crashmover_pool.free_count() > 0:
            self.crashmover_pool.spawn(self.crashmover_process_queue)

    def add_crashreport(self, raw_crash, dumps, crash_id):
        """Add a new crash report to the crashmover queue.

        :arg raw_crash: map of key/val crash annotations
        :arg dumps: map of name to memory dump
        :arg crash_id: the crash id for the crash report

        """
        crash_report = CrashReport(raw_crash, dumps, crash_id)
        crash_report.set_state(STATE_SAVE)

        self.crashmover_queue.append(crash_report)
        self.hb_run_crashmover()

    def crashmover_process_queue(self):
        """Process crashmover work.

        NOTE(willkg): This has to be super careful not to lose crash reports.
        If there's any kind of problem, this must return the crash report to
        the relevant queue.

        """
        while self.crashmover_queue:
            crash_report = self.crashmover_queue.popleft()
            try:
                if crash_report.state == STATE_SAVE:
                    # Save crash and then toss crash_id in the publish queue
                    self.crashmover_save(crash_report)
                    crash_report.set_state(STATE_PUBLISH)
                    self.crashmover_queue.append(crash_report)

                elif crash_report.state == STATE_PUBLISH:
                    # Publish crash and we're done
                    self.crashmover_publish(crash_report)
                    self.crashmover_finish(crash_report)

            except Exception:
                MYMETRICS.incr("%s_crash_exception.count" % crash_report.state)
                crash_report.errors += 1
                LOGGER.exception(
                    "Exception when processing queue (%s), state: %s; error %d/%d",
                    crash_report.crash_id,
                    crash_report.state,
                    crash_report.errors,
                    MAX_ATTEMPTS,
                )

                # After MAX_ATTEMPTS, we give up on this crash and move on
                if crash_report.errors < MAX_ATTEMPTS:
                    self.crashmover_queue.append(crash_report)
                else:
                    LOGGER.error(
                        "%s: too many errors trying to %s; dropped",
                        crash_report.crash_id,
                        crash_report.state,
                    )
                    MYMETRICS.incr("%s_crash_dropped.count" % crash_report.state)

    def crashmover_finish(self, crash_report):
        """Finish bookkeeping on crash report."""
        # Capture the total time it took for this crash to be handled from
        # being received from breakpad client to saving to s3.
        #
        # NOTE(willkg): We use submitted_timestamp which is formatted with isoformat().
        # time.time() returns seconds as a float, but .timing() wants milliseconds, so
        # we multiply by 1000.

        delta = time.time() - isoformat_to_time(
            crash_report.raw_crash["submitted_timestamp"]
        )
        delta = delta * 1000

        MYMETRICS.timing("crash_handling.time", value=delta)
        MYMETRICS.incr("save_crash.count")

    @MYMETRICS.timer("crash_save.time")
    def crashmover_save(self, crash_report):
        """Save crash report to storage."""
        self.crashstorage.save_crash(crash_report)
        LOGGER.info("%s saved", crash_report.crash_id)

    @MYMETRICS.timer("crash_publish.time")
    def crashmover_publish(self, crash_report):
        """Publish crash_id in publish queue."""
        self.crashpublish.publish_crash(crash_report)
        LOGGER.info("%s published", crash_report.crash_id)

    def join_pool(self):
        """Join the pool.

        NOTE(willkg): Only use this in tests!

        This is helpful for forcing all the coroutines in the pool to complete
        so that we can verify outcomes in the test suite for work that might
        cross coroutines.

        """
        self.crashmover_pool.join()
