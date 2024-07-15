# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from pathlib import Path
import sys

from click.testing import CliRunner

# Add bin/ directory so we can import scripts
REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT / "bin"))


class TestPubSubCli:
    def test_basic(self):
        """Basic test to make sure pubsub_cli imports and runs at all."""
        from pubsub_cli import pubsub_group

        runner = CliRunner()
        result = runner.invoke(pubsub_group, [])
        assert result.exit_code == 0


class TestGcsCli:
    def test_basic(self):
        """Basic test to make sure gcs_cli imports and runs at all."""
        from gcs_cli import gcs_group

        runner = CliRunner()
        result = runner.invoke(gcs_group, [])
        assert result.exit_code == 0
