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
    """This is a no-op crash storage that just logs that it could have saved a crash"""
    def save_raw_crash(self, raw_crash, dumps, crash_id):
        logger.info('crash no-op: %s %s %s', crash_id, raw_crash, dumps.keys())
