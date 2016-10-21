# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re

from everett.manager import ConfigManager

from antenna.throttler import Rule, Throttler, ACCEPT, DEFER, REJECT


class TestRule:
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

        answer, percent = throttler.throttle(
            '11234',
            {'ProductName': 'Test'}
        )

        assert answer is ACCEPT


class Testmozilla_rules:
    # NOTE(willkg): This is a rewrite of existing throttler tests in Socorro.

    def test_hangid(self, loggingmock):
        raw_crash = {
            'ProductName': 'FireSquid',
            'Version': '99',
            'ProcessType': 'browser',
            'HangID': 'xyz'
        }

        with loggingmock(['antenna']) as lm:
            throttler = Throttler(ConfigManager.from_dict({}))
            answer, percent = throttler.throttle('11234', raw_crash)

            # Reject anything with a HangId and ProcessType = 'browser'
            assert answer is REJECT
            assert percent is None

            assert lm.has_record(
                name='antenna.throttler',
                levelname='DEBUG',
                msg_contains='has_hangid_and_browser'
            )

    def test_comments(self):
        raw_crash = {
            'ProductName': 'Test',
            'Comments': 'foo bar baz'
        }

        throttler = Throttler(ConfigManager.from_dict({}))
        answer, percent = throttler.throttle('11234', raw_crash)

        # Reject anything with a HangId and ProcessType = 'browser'
        assert answer is ACCEPT
        assert percent is 100
