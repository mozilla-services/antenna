# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from pathlib import Path
import sys

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "bin"))


class TestPubSubCli:
    def test_basic(self):
        """Basic test to make sure pubsub_cli imports and runs at all."""
        from pubsub_cli import pubsub_group

        runner = CliRunner()
        result = runner.invoke(pubsub_group, [])
        assert result.exit_code == 0


class TestS3Cli:
    def test_basic(self):
        """Basic test to make sure s3_cli imports and runs at all."""
        from s3_cli import s3_group

        runner = CliRunner()
        result = runner.invoke(s3_group, [])
        assert result.exit_code == 0


class TestSQSCli:
    def test_basic(self):
        """Basic test to make sure sqs_cli imports and runs at all."""
        from sqs_cli import sqs_group

        runner = CliRunner()
        result = runner.invoke(sqs_group, [])
        assert result.exit_code == 0
