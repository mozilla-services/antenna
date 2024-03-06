# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from pathlib import Path
import sys

from everett.manager import ConfigManager, ConfigDictEnv, ConfigOSEnv
from falcon.request import Request
from falcon.testing.helpers import create_environ
from falcon.testing.client import TestClient
import markus
import pytest


# Add repository root so we can import antenna.
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from antenna.app import get_app, setup_logging  # noqa: E402
from antenna.app import reset_verify_funs  # noqa: E402
import antenna.libmarkus  # noqa: E402


def pytest_runtest_setup():
    # Make sure we set up logging and metrics to sane default values.
    setup_logging(logging_level="DEBUG", debug=True, host_id="", processname="antenna")
    markus.configure([{"class": "markus.backends.logging.LoggingMetrics"}])
    # prevent antenna from reconfiguring markus
    antenna.libmarkus._IS_MARKUS_SETUP = True

    # Wipe any registered verify functions
    reset_verify_funs()


@pytest.fixture
def request_generator():
    """Returns a Falcon Request generator"""

    def _request_generator(method, path, query_string=None, headers=None, body=None):
        env = create_environ(
            method=method,
            path=path,
            query_string=(query_string or ""),
            headers=headers,
            body=body,
        )
        return Request(env)

    return _request_generator


class AntennaTestClient(TestClient):
    """Test client to ease testing with Antenna API"""

    @classmethod
    def build_config(cls, new_config=None):
        """Build ConfigManager using environment and overrides."""
        new_config = new_config or {}
        config_manager = ConfigManager(
            environments=[ConfigDictEnv(new_config), ConfigOSEnv()]
        )
        return config_manager

    def rebuild_app(self, new_config):
        """Rebuilds the app

        This is helpful if you've changed configuration and need to rebuild the
        app so that components pick up the new configuration.

        :arg new_config: dict of configuration to override normal values to build the
            new app with

        """
        self.app = get_app(self.build_config(new_config))

    def get_crashmover(self):
        """Retrieves the crashmover from the AntennaApp."""
        return self.app.app.crashmover

    def get_resource_by_name(self, name):
        """Retrieves the Falcon API resource by name"""
        return self.app.app.get_resource_by_name(name)


@pytest.fixture
def client():
    """Test client for the Antenna API

    This creates an app and a test client that uses that app to submit HTTP
    GET/POST requests.

    The app that's created uses configuration defaults. If you need it to use
    an app with a different configuration, you can rebuild the app with
    different configuration::

        def test_foo(client, tmpdir):
            client.rebuild_app({
                'BASEDIR': str(tmpdir)
            })

    """
    return AntennaTestClient(get_app(AntennaTestClient.build_config()))
