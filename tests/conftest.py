import os

import pytest
from webtest import TestApp

from antenna.wsgi import app as antenna_app


@pytest.fixture
def testapp():
    return TestApp(antenna_app)


@pytest.fixture
def datadir():
    return os.path.join(os.path.dirname(__file__), 'data')
