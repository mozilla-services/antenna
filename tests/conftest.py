# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import pytest
import sys
from webtest import TestApp

# Add the parent directory to the sys.path so that it can import the antenna
# code.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


from antenna.app import get_app  # noqa


@pytest.fixture
def testapp():
    return TestApp(get_app())


@pytest.fixture
def datadir():
    return os.path.join(os.path.dirname(__file__), 'data')
