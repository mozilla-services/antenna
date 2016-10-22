# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re

from everett.manager import ConfigManager
import pytest

from antenna.throttler import Rule, Throttler, ACCEPT, DEFER, REJECT


class TestRule:
    def test_invalid_rule_name(self):
        with pytest.raises(ValueError):
            Rule('o m g!', '*', lambda x: True, 100)

    def test_star(self):
        def is_crash(thing):
            return isinstance(thing, dict)

        # Asserts that the is_crash condition function got a crash as an
        # argument.
        rule = Rule('test', '*', is_crash, 100)
        assert rule.match({'ProductName': 'test'}) is True

        # Asserts that the is_crash condition function did not get a crash as
        # an argument.
        rule = Rule('test', 'ProductName', is_crash, 100)
        assert rule.match({'ProductName': 'Test'}) is False

    def test_condition_function(self):
        rule = Rule('test', '*', lambda x: True, 100)
        assert rule.match({'ProductName': 'test'}) is True

        rule = Rule('test', '*', lambda x: False, 100)
        assert rule.match({'ProductName': 'test'}) is False

    def test_condition_regexp(self):
        rule = Rule('test', 'ProductName', re.compile('^test'), 100)
        assert rule.match({'ProductName': 'testabc'}) is True
        assert rule.match({'ProductName': 'abc'}) is False

    def test_condition_value(self):
        rule = Rule('test', 'ProductName', 'test', 100)
        assert rule.match({'ProductName': 'test'}) is True
        assert rule.match({'ProductName': 'testabc'}) is False

        rule = Rule('test', 'Version', 1.0, 100)
        assert rule.match({'Version': 1.0}) is True
        assert rule.match({'Version': 2.0}) is False

        assert rule.match({'ProductName': 'testabc'}) is False

    def test_percentage(self, randommock):
        throttler = Throttler(ConfigManager.from_dict({}))

        # Overrwrite the rule set for something we need
        throttler.rule_set = [
            Rule('test', 'ProductName', 'test', 50)
        ]

        with randommock(0.45):
            # Below the percentage line, so ACCEPT!
            assert throttler.throttle('11234', {'ProductName': 'test'}) == (ACCEPT, 50)

        with randommock(0.55):
            # Above the percentage line, so DEFER!
            assert throttler.throttle('11234', {'ProductName': 'test'}) == (DEFER, 50)


class Testaccept_all:
    def test_ruleset(self):
        throttler = Throttler(ConfigManager.from_dict({
            'THROTTLE_RULES': 'antenna.throttler.accept_all'
        }))

        assert throttler.throttle('11234', {'ProductName': 'Test'}) == (ACCEPT, 100)


class Testmozilla_rules:
    def test_hangid(self, loggingmock):
        raw_crash = {
            'ProductName': 'FireSquid',
            'Version': '99',
            'ProcessType': 'browser',
            'HangID': 'xyz'
        }

        with loggingmock(['antenna']) as lm:
            throttler = Throttler(ConfigManager.from_dict({}))

            # Reject anything with a HangId and ProcessType = 'browser'
            assert throttler.throttle('11234', raw_crash) == (REJECT, None)

            assert lm.has_record(
                name='antenna.throttler',
                levelname='DEBUG',
                msg_contains='has_hangid_and_browser'
            )

    def test_comments(self, loggingmock):
        raw_crash = {
            'ProductName': 'Test',
            'Comments': 'foo bar baz'
        }

        with loggingmock(['antenna']) as lm:
            throttler = Throttler(ConfigManager.from_dict({}))

            assert throttler.throttle('11234', raw_crash) == (ACCEPT, 100)

            assert lm.has_record(
                name='antenna.throttler',
                levelname='DEBUG',
                msg_contains='has_comments'
            )

    @pytest.mark.parametrize('channel', [
        'aurora',
        'beta',
        'esr'
    ])
    def test_is_alpha_beta_esr(self, channel, loggingmock):
        raw_crash = {
            'ProductName': 'Test',
            'ReleaseChannel': channel
        }

        with loggingmock(['antenna']) as lm:
            throttler = Throttler(ConfigManager.from_dict({}))

            assert throttler.throttle('11234', raw_crash) == (ACCEPT, 100)

            assert lm.has_record(
                name='antenna.throttler',
                levelname='DEBUG',
                msg_contains='is_alpha_beta_esr'
            )

    @pytest.mark.parametrize('channel', [
        'nightly',
        'nightlyfoo'
    ])
    def test_is_nightly(self, channel, loggingmock):
        raw_crash = {
            'ProductName': 'Test',
            'ReleaseChannel': channel
        }
        with loggingmock(['antenna']) as lm:
            throttler = Throttler(ConfigManager.from_dict({}))

            assert throttler.throttle('11234', raw_crash) == (ACCEPT, 100)

            assert lm.has_record(
                name='antenna.throttler',
                levelname='DEBUG',
                msg_contains='is_nightly'
            )

    def test_is_firefox(self, randommock, loggingmock):
        with randommock(0.09):
            raw_crash = {
                'ProductName': 'Firefox',
            }
            with loggingmock(['antenna']) as lm:
                throttler = Throttler(ConfigManager.from_dict({}))

                assert throttler.throttle('11234', raw_crash) == (ACCEPT, 10)

                assert lm.has_record(
                    name='antenna.throttler',
                    levelname='DEBUG',
                    msg_contains='is_firefox'
                )

        with randommock(0.9):
            raw_crash = {
                'ProductName': 'Firefox',
            }
            with loggingmock(['antenna']) as lm:
                throttler = Throttler(ConfigManager.from_dict({}))

                assert throttler.throttle('11234', raw_crash) == (DEFER, 10)

                assert lm.has_record(
                    name='antenna.throttler',
                    levelname='DEBUG',
                    msg_contains='is_firefox'
                )

    def test_is_fennec(self, loggingmock):
        raw_crash = {
            'ProductName': 'Fennec'
        }
        with loggingmock(['antenna']) as lm:
            throttler = Throttler(ConfigManager.from_dict({}))

            assert throttler.throttle('11234', raw_crash) == (ACCEPT, 100)

            assert lm.has_record(
                name='antenna.throttler',
                levelname='DEBUG',
                msg_contains='is_fennec'
            )

    @pytest.mark.parametrize('version', [
        '35.0a',
        '35.0b',
        '35.0A',
        '35.0.0a'
    ])
    def test_is_version_alpha_beta_special(self, version, loggingmock):
        raw_crash = {
            'ProductName': 'Test',
            'Version': version
        }
        with loggingmock(['antenna']) as lm:
            throttler = Throttler(ConfigManager.from_dict({}))

            assert throttler.throttle('11234', raw_crash) == (ACCEPT, 100)

            assert lm.has_record(
                name='antenna.throttler',
                levelname='DEBUG',
                msg_contains='is_version_alpha_beta_special'
            )

    @pytest.mark.parametrize('product', [
        'Thunderbird',
        'Seamonkey'
    ])
    def test_is_thunderbird_seamonkey(self, product, loggingmock):
        raw_crash = {
            'ProductName': product
        }
        with loggingmock(['antenna']) as lm:
            throttler = Throttler(ConfigManager.from_dict({}))

            assert throttler.throttle('11234', raw_crash) == (ACCEPT, 100)

            assert lm.has_record(
                name='antenna.throttler',
                levelname='DEBUG',
                msg_contains='is_thunderbird_seamonkey'
            )
