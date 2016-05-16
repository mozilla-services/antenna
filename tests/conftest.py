import os

import pytest


@pytest.fixture
def datadir():
    return os.path.join(os.path.dirname(__file__), 'data')
