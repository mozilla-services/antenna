# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import contextlib
from pathlib import Path
import sys
from unittest import mock

from markus.testing import MetricsMock
import pytest


# Add repository root so we can import testlib.
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from testlib.s3mock import S3Mock  # noqa


@pytest.fixture
def s3mock():
    """Returns an s3mock context that lets you do S3-related tests

    Usage::

        def test_something(s3mock):
            s3mock.add_step(
                method='PUT',
                url='...'
                resp=s3mock.fake_response(status_code=200)
            )

    """
    with S3Mock() as s3:
        yield s3


@pytest.fixture
def metricsmock():
    """Returns MetricsMock that a context to record metrics records

    Usage::

        def test_something(metricsmock):
            with metricsmock as mm:
                # do stuff
                assert mm.has_record(
                    stat='some.stat',
                    kwargs_contains={
                        'something': 1
                    }
                )

    """
    return MetricsMock()


@pytest.fixture
def randommock():
    """Returns a contextmanager that mocks random.random() at a specific value

    Usage::

        def test_something(randommock):
            with randommock(0.55):
                # test stuff...

    """

    @contextlib.contextmanager
    def _randommock(value):
        with mock.patch("random.random") as mock_random:
            mock_random.return_value = value
            yield

    return _randommock
