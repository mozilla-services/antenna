# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re

from everett.manager import ConfigManager
import pytest

from antenna.throttler import (
    ACCEPT,
    DEFER,
    REJECT,
    Rule,
    Throttler,
    match_infobar_true,
    match_firefox_pre_57,
)


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


class Testmatch_infobar_true:
    @pytest.mark.parametrize('version, expected', [
        # Before 52 is fine
        ('51.0', False),

        # After 59 is fine
        ('60.0', False),

        # Anything in the middle is not fine
        ('59.0', True),
        ('58.0', True),
        ('57.0', True),
        ('57.0.2', True),
        ('56.0', True),
        ('55.0', True),
        ('54.0', True),
        ('53.0', True),
        ('52.0', True),
    ])
    def test_versions(self, version, expected):
        raw_crash = {
            'ProductName': 'Firefox',
            'SubmittedFromInfobar': 'true',
            'BuildID': '20171128222554',
            'Version': version
        }
        assert match_infobar_true(raw_crash) == expected

    def test_product_name(self):
        # No ProductName
        raw_crash = {
            'SubmittedFromInfobar': 'true',
            'BuildID': '20171128222554',
            'Version': '57.0'
        }
        assert match_infobar_true(raw_crash) is False

        # ProductName is not Firefox
        raw_crash = {
            'ProductName': 'FishSplat',
            'SubmittedFromInfobar': 'true',
            'BuildID': '20171128222554',
            'Version': '57.0'
        }
        assert match_infobar_true(raw_crash) is False

    def test_submittedinfobar(self):
        # No SubmittedFromInfobar
        raw_crash = {
            'ProductName': 'Firefox',
            'BuildID': '20171128222554',
            'Version': '57.0'
        }
        assert match_infobar_true(raw_crash) is False

        # False SubmittedFromInfobar
        raw_crash = {
            'ProductName': 'Firefox',
            'SubmittedFromInfobar': 'false',
            'BuildID': '20171128222554',
            'Version': '57.0'
        }
        assert match_infobar_true(raw_crash) is False

    def test_buildid(self):
        # FIXME(willkg): You might have to update this test when you update the buildid.
        # No BuildID
        raw_crash = {
            'ProductName': 'Firefox',
            'SubmittedFromInfobar': 'true',
            'Version': '57.0'
        }
        assert match_infobar_true(raw_crash) is False

        # BuildID that falls into range triggers rule.
        raw_crash = {
            'ProductName': 'Firefox',
            'SubmittedFromInfobar': 'true',
            'BuildID': '20171128222554',
            'Version': '57.0'
        }
        assert match_infobar_true(raw_crash) is True

        # BuildID after range doesn't trigger rule.
        raw_crash = {
            'ProductName': 'Firefox',
            'SubmittedFromInfobar': 'true',
            'BuildID': '20171226003912',
            'Version': '57.0'
        }
        assert match_infobar_true(raw_crash) is False


class Test_match_firefox_pre_57:
    @pytest.mark.parametrize('version, expected', [
        # Before 57 match
        ('56.0', True),
        ('56.0.2', True),
        ('55.0', True),
        ('5.0', True),

        # 57 and after does not match
        ('57.0', False),
        ('57.0.1', False),
        ('60.0', False),

        # Junk versions don't match
        ('abc', False),
    ])
    def test_versions(self, version, expected):
        raw_crash = {
            'ProductName': 'Firefox',
            'Version': version
        }
        assert match_firefox_pre_57(raw_crash) == expected

    def test_no_version(self):
        raw_crash = {
            'ProductName': 'Firefox',
        }
        assert match_firefox_pre_57(raw_crash) is False

    def test_product(self):
        # No ProductName
        raw_crash = {
            'Version': '56.0'
        }
        assert match_firefox_pre_57(raw_crash) is False

        # ProductName is not Firefox
        raw_crash = {
            'ProductName': 'FishSplat',
            'Version': '56.0'
        }
        assert match_firefox_pre_57(raw_crash) is False


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

    def test_infobar(self):
        raw_crash = {
            'ProductName': 'Firefox',
            'SubmittedFromInfobar': 'true',
            'Version': '52.0.2',
            'BuildID': '20171223222554',
        }
        throttler = Throttler(ConfigManager.from_dict({}))
        assert throttler.throttle(raw_crash) == (REJECT, 'infobar_is_true', None)

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
