import os
import pytest
from webtest import TestApp

from antenna.app import get_app


@pytest.fixture
def testapp():
    return TestApp(get_app())


@pytest.fixture
def datadir():
    return os.path.join(os.path.dirname(__file__), 'data')
