from antenna import sentry


def test_capture_unhandled_exceptions_no_client(loggingmock):
    """Verify _sentry_client=None -> logging no sentry client set up"""
    try:
        old_val = sentry._sentry_client
        with loggingmock(['antenna']) as lm:
            sentry._sentry_client = None

            try:
                with sentry.capture_unhandled_exceptions():
                    1 / 0
            except ZeroDivisionError:
                pass

            assert lm.has_record(
                name='antenna.sentry',
                levelname='WARNING',
                msg_contains='No Sentry client set up.'
            )

    finally:
        sentry._sentry_client = old_val


def test_capture_unhandled_exceptions_sentry(loggingmock):
    """Verify _sentry_client=Sentry sends things to sentry"""
    class FakeSentry:
        def __init__(self):
            self.capture_called = 0

        def captureException(self):
            self.capture_called += 1

    try:
        old_val = sentry._sentry_client

        with loggingmock(['antenna']) as lm:
            sentry._sentry_client = FakeSentry()

            try:
                with sentry.capture_unhandled_exceptions():
                    1 / 0
            except ZeroDivisionError:
                pass

            assert lm.has_record(
                name='antenna.sentry',
                levelname='INFO',
                msg_contains='Unhandled exception sent to sentry.'
            )

            assert sentry._sentry_client.capture_called == 1

    finally:
        sentry._sentry_client = old_val
