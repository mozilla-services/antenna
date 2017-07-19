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
            assert throttler.throttle({'ProductName': 'test'}) == (ACCEPT, 'test', 50)

        with randommock(0.55):
            # Above the percentage line, so DEFER!
            assert throttler.throttle({'ProductName': 'test'}) == (DEFER, 'test', 50)


class Testaccept_all:
    def test_ruleset(self):
        throttler = Throttler(ConfigManager.from_dict({
            'THROTTLE_RULES': 'antenna.throttler.accept_all'
        }))

        assert throttler.throttle({'ProductName': 'Test'}) == (ACCEPT, 'accept_everything', 100)


class Testmozilla_rules:
    def test_hangid(self):
        raw_crash = {
            'ProductName': 'FireSquid',
            'Version': '99',
            'ProcessType': 'browser',
            'HangID': 'xyz'
        }

        throttler = Throttler(ConfigManager.from_dict({}))
        assert throttler.throttle(raw_crash) == (REJECT, 'has_hangid_and_browser', None)

    def test_comments(self):
        raw_crash = {
            'ProductName': 'Test',
            'Comments': 'foo bar baz'
        }

        throttler = Throttler(ConfigManager.from_dict({}))
        assert throttler.throttle(raw_crash) == (ACCEPT, 'has_comments', 100)

    @pytest.mark.parametrize('channel', [
        'aurora',
        'beta',
        'esr'
    ])
    def test_is_alpha_beta_esr(self, channel):
        raw_crash = {
            'ProductName': 'Test',
            'ReleaseChannel': channel
        }

        throttler = Throttler(ConfigManager.from_dict({}))
        assert throttler.throttle(raw_crash) == (ACCEPT, 'is_alpha_beta_esr', 100)

    @pytest.mark.parametrize('channel', [
        'nightly',
        'nightlyfoo'
    ])
    def test_is_nightly(self, channel):
        raw_crash = {
            'ProductName': 'Test',
            'ReleaseChannel': channel
        }

        throttler = Throttler(ConfigManager.from_dict({}))
        assert throttler.throttle(raw_crash) == (ACCEPT, 'is_nightly', 100)

    def test_is_firefox(self, randommock):
        with randommock(0.09):
            raw_crash = {
                'ProductName': 'Firefox',
            }

            throttler = Throttler(ConfigManager.from_dict({}))
            assert throttler.throttle(raw_crash) == (ACCEPT, 'is_firefox_desktop', 10)

        with randommock(0.9):
            raw_crash = {
                'ProductName': 'Firefox',
            }

            throttler = Throttler(ConfigManager.from_dict({}))
            assert throttler.throttle(raw_crash) == (DEFER, 'is_firefox_desktop', 10)

    def test_is_fennec(self):
        raw_crash = {
            'ProductName': 'Fennec'
        }

        throttler = Throttler(ConfigManager.from_dict({}))
        assert throttler.throttle(raw_crash) == (ACCEPT, 'is_fennec', 100)

    @pytest.mark.parametrize('version', [
        '35.0a',
        '35.0b',
        '35.0A',
        '35.0.0a'
    ])
    def test_is_version_alpha_beta_special(self, version):
        raw_crash = {
            'ProductName': 'Test',
            'Version': version
        }

        throttler = Throttler(ConfigManager.from_dict({}))
        assert throttler.throttle(raw_crash) == (ACCEPT, 'is_version_alpha_beta_special', 100)

    @pytest.mark.parametrize('product', [
        'Thunderbird',
        'Seamonkey'
    ])
    def test_is_thunderbird_seamonkey(self, product):
        raw_crash = {
            'ProductName': product
        }

        throttler = Throttler(ConfigManager.from_dict({}))
        assert throttler.throttle(raw_crash) == (ACCEPT, 'is_thunderbird_seamonkey', 100)

    def test_is_nothing(self):
        # None of the rules will match an empty crash
        raw_crash = {}

        throttler = Throttler(ConfigManager.from_dict({}))
        assert throttler.throttle(raw_crash) == (DEFER, 'NO_MATCH', 0)

    def test_bad_value(self):
        raw_crash = {
            'ProductName': ''
        }

        throttler = Throttler(ConfigManager.from_dict({}))
        assert throttler.throttle(raw_crash) == (DEFER, 'NO_MATCH', 0)
