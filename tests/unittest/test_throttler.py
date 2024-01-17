# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import json
import logging

from everett.manager import ConfigManager
from freezegun import freeze_time
import pytest

from antenna.throttler import (
    ACCEPT,
    REJECT,
    FAKEACCEPT,
    Rule,
    Throttler,
    match_infobar_true,
    match_old_buildid,
    match_unsupported_windows,
)


@pytest.fixture
def throttler():
    return Throttler(
        ConfigManager.from_dict({"PRODUCTS": "antenna.throttler.ALL_PRODUCTS"})
    )


class TestRule:
    def test_invalid_rule_name(self):
        with pytest.raises(ValueError):
            Rule("o m g!", "*", lambda throttler, x: True, ACCEPT)

    def test_star(self, throttler):
        def is_crash(throttler, thing):
            return isinstance(thing, dict)

        # Asserts that the is_crash condition function got a crash as an
        # argument.
        rule = Rule("test", "*", is_crash, ACCEPT)
        assert rule.match(throttler, {"ProductName": "test"}) is True

        # Asserts that the is_crash condition function did not get a crash as
        # an argument.
        rule = Rule("test", "ProductName", is_crash, ACCEPT)
        assert rule.match(throttler, {"ProductName": "Test"}) is False

    def test_condition_function_star(self, throttler):
        rule = Rule("test", "*", lambda throttler, x: True, ACCEPT)
        assert rule.match(throttler, {"ProductName": "test"}) is True

        rule = Rule("test", "*", lambda throttler, x: False, ACCEPT)
        assert rule.match(throttler, {"ProductName": "test"}) is False

    def test_condition_function_value(self, throttler):
        rule = Rule("test", "Foo", lambda throttler, x: x.startswith("bar"), ACCEPT)
        assert rule.match(throttler, {"Foo": "bar"}) is True
        assert rule.match(throttler, {"Foo": "piano"}) is False
        assert rule.match(throttler, {"Foo": None}) is False

    def test_percentage(self, throttler, randommock):
        # Overrwrite the rule set for something we need
        throttler.rule_set = [
            Rule(
                "test",
                "ProductName",
                lambda throttler, x: x == "test",
                (50, ACCEPT, REJECT),
            )
        ]

        with randommock(0.45):
            # Below the percentage line, so ACCEPT!
            assert throttler.throttle({"ProductName": "test"}) == (ACCEPT, "test", 50)

        with randommock(0.55):
            # Above the percentage line, so DEFER!
            assert throttler.throttle({"ProductName": "test"}) == (REJECT, "test", 50)


class TestACCEPT_ALL:
    def test_ruleset(self):
        throttler = Throttler(
            ConfigManager.from_dict({"RULES": "antenna.throttler.ACCEPT_ALL"})
        )

        assert throttler.throttle({"ProductName": "Test"}) == (
            ACCEPT,
            "accept_everything",
            100,
        )


class Test_match_infobar_true:
    @pytest.mark.parametrize(
        "version, expected",
        [
            # Before 52 is fine
            ("51.0", False),
            # After 59 is fine
            ("60.0", False),
            # Anything in the middle is not fine
            ("59.0", True),
            ("58.0", True),
            ("57.0", True),
            ("57.0.2", True),
            ("56.0", True),
            ("55.0", True),
            ("54.0", True),
            ("53.0", True),
            ("52.0", True),
        ],
    )
    def test_versions(self, throttler, version, expected):
        raw_crash = {
            "ProductName": "Firefox",
            "SubmittedFromInfobar": "true",
            "BuildID": "20171128222554",
            "Version": version,
        }
        assert match_infobar_true(throttler, raw_crash) == expected

    def test_product_name(self, throttler):
        # No ProductName
        raw_crash = {
            "SubmittedFromInfobar": "true",
            "BuildID": "20171128222554",
            "Version": "57.0",
        }
        assert match_infobar_true(throttler, raw_crash) is False

        # ProductName is not Firefox
        raw_crash = {
            "ProductName": "FishSplat",
            "SubmittedFromInfobar": "true",
            "BuildID": "20171128222554",
            "Version": "57.0",
        }
        assert match_infobar_true(throttler, raw_crash) is False

    def test_submittedinfobar(self, throttler):
        # No SubmittedFromInfobar
        raw_crash = {
            "ProductName": "Firefox",
            "BuildID": "20171128222554",
            "Version": "57.0",
        }
        assert match_infobar_true(throttler, raw_crash) is False

        # False SubmittedFromInfobar
        raw_crash = {
            "ProductName": "Firefox",
            "SubmittedFromInfobar": "false",
            "BuildID": "20171128222554",
            "Version": "57.0",
        }
        assert match_infobar_true(throttler, raw_crash) is False

    def test_buildid(self, throttler):
        # NOTE(willkg): You might have to update this test when you update the buildid.

        # No BuildID
        raw_crash = {
            "ProductName": "Firefox",
            "SubmittedFromInfobar": "true",
            "Version": "57.0",
        }
        assert match_infobar_true(throttler, raw_crash) is False

        # BuildID that falls into range triggers rule.
        raw_crash = {
            "ProductName": "Firefox",
            "SubmittedFromInfobar": "true",
            "BuildID": "20171128222554",
            "Version": "57.0",
        }
        assert match_infobar_true(throttler, raw_crash) is True

        # BuildID after range doesn't trigger rule.
        raw_crash = {
            "ProductName": "Firefox",
            "SubmittedFromInfobar": "true",
            "BuildID": "20171226003912",
            "Version": "57.0",
        }
        assert match_infobar_true(throttler, raw_crash) is False


class Test_match_unsupported_windows:
    @pytest.mark.parametrize(
        "data",
        [
            {},
            {"TelemetryEnvironment": "{}"},
            {"TelemetryEnvironment": '{"system":{}}'},
            {"TelemetryEnvironment": '{"system":{"os":{}}}'},
            {"TelemetryEnvironment": '{"system":{"os":{"name":""}}}'},
            {"TelemetryEnvironment": '{"system":{"os":{"name":"Windows_NT"}}}'},
            {
                "TelemetryEnvironment": '{"system":{"os":{"name":"Windows_NT","windowsBuildNumber":""}}}'
            },
            {
                "TelemetryEnvironment": '{"system":{"os":{"name":"Windows_NT","windowsBuildNumber":null}}}'
            },
        ],
    )
    def test_missing_data(self, throttler, data):
        assert match_unsupported_windows(throttler, data) is False

    @pytest.mark.parametrize(
        "version, expected",
        [
            # Windows 7
            (7601, True),
            # Windows 8
            (9200, True),
            # Windows 8.1
            (9600, True),
            # Windows 10
            (10240, False),
        ],
    )
    def test_windows_versions(self, throttler, version, expected):
        data = {
            "TelemetryEnvironment": json.dumps(
                {
                    "system": {
                        "os": {
                            "name": "Windows_NT",
                            "windowsBuildNumber": version,
                        },
                    },
                }
            )
        }
        assert match_unsupported_windows(throttler, data) is expected


class Test_match_old_buildid:
    def test_no_buildid(self, throttler):
        assert match_old_buildid(throttler, {}) is False

    @pytest.mark.parametrize(
        "buildid, expected",
        [
            ("", False),
            ("None", False),
            (None, False),
            ("abc", False),
            ("20220404", False),
            ("11111111111111", False),
        ],
    )
    def test_bad_data(self, throttler, buildid, expected):
        raw_crash = {"BuildID": buildid}
        assert match_old_buildid(throttler, raw_crash) == expected

    @pytest.mark.parametrize(
        "buildid, expected",
        [
            # These are too old
            ("20170101000000", True),
            ("20180101000000", True),
            ("20180528000000", True),
            # This is just under 730 days ago
            ("20180529000000", False),
            ("20180530000000", False),
            # This is now
            ("20200527000000", False),
        ],
    )
    @freeze_time("2020-05-27 12:00:00", tz_offset=0)
    def test_valid_buildis(self, throttler, buildid, expected):
        raw_crash = {"BuildID": buildid}
        assert match_old_buildid(throttler, raw_crash) == expected


class Testmozilla_rules:
    def test_bad_data(self, throttler):
        # NOTE(willkg): We use the test throttler which supports all products, so this
        # gets through all the rules.
        raw_crash = {
            "ProductName": None,
            "Version": None,
            "BuildID": None,
            "ReleaseChannel": None,
        }
        assert throttler.throttle(raw_crash) == (ACCEPT, "accept_everything", 100)

    def test_old_buildid(self, throttler):
        raw_crash = {
            "ProductName": "FireSquid",
            "BuildID": "20170505000000",
        }
        assert throttler.throttle(raw_crash) == (REJECT, "has_old_buildid", 100)

    def test_hangid(self, throttler):
        raw_crash = {
            "ProductName": "FireSquid",
            "Version": "99",
            "ProcessType": "browser",
            "HangID": "xyz",
        }
        assert throttler.throttle(raw_crash) == (REJECT, "has_hangid_and_browser", 100)

    @freeze_time("2019-05-27 12:00:00", tz_offset=0)
    def test_infobar(self, throttler):
        raw_crash = {
            "ProductName": "Firefox",
            "SubmittedFromInfobar": "true",
            "Version": "52.0.2",
            "BuildID": "20171223222554",
        }
        assert throttler.throttle(raw_crash) == (REJECT, "infobar_is_true", 100)

    @pytest.mark.parametrize(
        "productname, expected",
        [
            # Test empty string
            ("", (REJECT, "unsupported_product", 100)),
            # Lowercase of existing product--product names are case-sensitive
            ("firefox", (REJECT, "unsupported_product", 100)),
            # This product doesn't exist in the list--unsupported
            ("testproduct", (REJECT, "unsupported_product", 100)),
        ],
    )
    def test_productname_reject(self, caplog, productname, expected):
        """Verify productname rule blocks unsupported products"""
        with caplog.at_level(logging.INFO, logger="antenna"):
            # Need a throttler with the default configuration which includes supported
            # products
            throttler = Throttler(ConfigManager.from_dict({}))
            raw_crash = {}
            if productname is not None:
                raw_crash["ProductName"] = productname
            assert throttler.throttle(raw_crash) == expected
            assert caplog.record_tuples == [
                (
                    "antenna.throttler",
                    logging.INFO,
                    "ProductName rejected: %r" % productname,
                )
            ]

    def test_productname_none_reject(self, caplog):
        """Verify productname rule blocks None value"""
        with caplog.at_level(logging.INFO, logger="antenna"):
            # Need a throttler with the default configuration which includes supported
            # products
            throttler = Throttler(ConfigManager.from_dict({}))
            raw_crash = {"ProductName": None}
            assert throttler.throttle(raw_crash) == (REJECT, "unsupported_product", 100)
            assert caplog.record_tuples == [
                ("antenna.throttler", logging.INFO, "ProductName rejected: 'None'")
            ]

    def test_productname_fakeaccept(self, caplog):
        # This product isn't in the list and it's B2G which is the special case
        with caplog.at_level(logging.INFO, logger="antenna"):
            # Need a throttler with the default configuration which includes supported
            # products
            throttler = Throttler(ConfigManager.from_dict({}))
            raw_crash = {"ProductName": "b2g"}
            assert throttler.throttle(raw_crash) == (FAKEACCEPT, "b2g", 100)
            assert caplog.record_tuples == [
                ("antenna.throttler", logging.INFO, "ProductName B2G: fake accept")
            ]

    def test_productname_no_unsupported_products(self):
        """Verify productname rule doesn't do anything if using ALL_PRODUCTS"""
        throttler = Throttler(
            ConfigManager.from_dict({"PRODUCTS": "antenna.throttler.ALL_PRODUCTS"})
        )
        raw_crash = {"ProductName": "testproduct"}
        # This is an unsupported product, but it's not accepted for processing
        # by any of the rules, so it gets caught up by the last rule
        assert throttler.throttle(raw_crash) == (ACCEPT, "accept_everything", 100)

    @pytest.mark.parametrize(
        "productname, packagename",
        [
            # Test packagename is accepted
            ("Fenix", "org.mozilla.firefox"),
            ("Focus", "org.mozilla.focus"),
            ("ReferenceBrowser", "org.mozilla.reference.browser"),
            # Test a product that has no Android packages
            ("Thunderbird", "org.example.fork"),
        ],
    )
    def test_packagename_accept(self, caplog, productname, packagename):
        """Verify supported packagename is accepted"""
        with caplog.at_level(logging.INFO, logger="antenna"):
            # Need a throttler with the default configuration which includes product ->
            # supported packagenames
            throttler = Throttler(ConfigManager.from_dict({}))
            raw_crash = {}
            raw_crash["ProductName"] = productname
            raw_crash["Android_PackageName"] = packagename

            assert throttler.throttle(raw_crash) == (ACCEPT, "accept_everything", 100)

    @pytest.mark.parametrize(
        "productname, packagename",
        [
            # Test empty packagename is rejected
            ("Fenix", ""),
            # Test supported product / unsupported packagename is rejected
            ("Fenix", "org.example.fork"),
            ("Focus", "org.example.fork"),
        ],
    )
    def test_packagename_reject(self, caplog, productname, packagename):
        """Verify unsupported packagename is rejected"""
        with caplog.at_level(logging.INFO, logger="antenna"):
            # Need a throttler with the default configuration which includes product ->
            # supported packagenames
            throttler = Throttler(ConfigManager.from_dict({}))
            raw_crash = {}
            raw_crash["ProductName"] = productname
            raw_crash["Android_PackageName"] = packagename

            assert throttler.throttle(raw_crash) == (
                REJECT,
                "unsupported_packagename",
                100,
            )
            assert caplog.record_tuples == [
                (
                    "antenna.throttler",
                    logging.INFO,
                    f"Android_PackageName rejected: {productname} '{packagename}'",
                )
            ]

    def test_packagename_reject_no_packagename(self, caplog):
        """Verify missing packagename for product that requires it is rejected"""
        with caplog.at_level(logging.INFO, logger="antenna"):
            # Need a throttler with the default configuration which includes product ->
            # supported packagenames
            throttler = Throttler(ConfigManager.from_dict({}))
            raw_crash = {}
            raw_crash["ProductName"] = "Fenix"

            assert throttler.throttle(raw_crash) == (
                REJECT,
                "unsupported_packagename",
                100,
            )
            assert caplog.record_tuples == [
                (
                    "antenna.throttler",
                    logging.INFO,
                    "Android_PackageName rejected: Fenix no Android_PackageName",
                )
            ]

    def test_packagename_no_unsupported_packagenames(self):
        """Verify packagename rule doesn't do anything if using ALL_PRODUCT_PACKAGENAMES"""
        throttler = Throttler(
            ConfigManager.from_dict(
                {"PRODUCT_PACKAGENAMES": "antenna.throttler.ALL_PRODUCT_PACKAGENAMES"}
            )
        )
        # Test supported product with no Android_PackageName, but no
        # product_packagenames set
        raw_crash = {"ProductName": "Fenix"}
        assert throttler.throttle(raw_crash) == (ACCEPT, "accept_everything", 100)

        # Test supported product with unsupported Android_PackageName, but no
        # product_packagenames set
        raw_crash = {
            "ProductName": "Fenix",
            "Android_PackageName": "org.example.fork",
        }
        assert throttler.throttle(raw_crash) == (ACCEPT, "accept_everything", 100)

    def test_throttleable(self, throttler):
        # Throttleable=0 should match
        raw_crash = {"ProductName": "Test", "Throttleable": "0"}
        assert throttler.throttle(raw_crash) == (ACCEPT, "throttleable_0", 100)

        # Any other value than "0" should not match
        raw_crash = {"ProductName": "Test", "Throttleable": "1"}
        assert throttler.throttle(raw_crash) != (ACCEPT, "throttleable_0", 100)

        raw_crash = {"ProductName": "Test", "Throttleable": "foo"}
        assert throttler.throttle(raw_crash) != (ACCEPT, "throttleable_0", 100)

    def test_comments(self, throttler):
        raw_crash = {"ProductName": "Test", "Comments": "foo bar baz"}
        assert throttler.throttle(raw_crash) == (ACCEPT, "has_comments", 100)

    def test_phc(self, throttler):
        raw_crash = {"ProductName": "Test", "PHCKind": "some value"}
        assert throttler.throttle(raw_crash) == (ACCEPT, "has_phc", 100)

    @pytest.mark.parametrize(
        "processtype, expected",
        [
            (None, (ACCEPT, "accept_everything", 100)),
            ("", (ACCEPT, "accept_everything", 100)),
            ("content", (ACCEPT, "accept_everything", 100)),
            ("gpu", (ACCEPT, "is_gpu", 100)),
        ],
    )
    def test_gpu(self, throttler, processtype, expected):
        raw_crash = {"ProductName": "BarTest"}
        if processtype:
            raw_crash["ProcessType"] = processtype
        assert throttler.throttle(raw_crash) == expected

    def test_is_shutdownkill(self, throttler, randommock):
        # Reject 90% of incoming ShutDownKill crash reports
        with randommock(0.9):
            raw_crash = {"ProductName": "Test", "ipc_channel_error": "ShutDownKill"}
            assert throttler.throttle(raw_crash) == (REJECT, "is_shutdownkill", 10)

        # Let the remaining 10% of ShutDownKill crash reports continue through the
        # throttle rules
        with randommock(0.09):
            raw_crash = {"ProductName": "Test", "ipc_channel_error": "ShutDownKill"}
            assert throttler.throttle(raw_crash) == (ACCEPT, "accept_everything", 100)

    def test_is_firefox_esr_unsupported_windows(self, throttler, randommock):
        tel_env = json.dumps(
            {
                "system": {
                    "os": {
                        "name": "Windows_NT",
                        "windowsBuildNumber": 9600,
                    },
                },
            }
        )
        raw_crash = {
            "ProductName": "Firefox",
            "ReleaseChannel": "esr",
            "TelemetryEnvironment": tel_env,
        }
        with randommock(0.30):
            assert throttler.throttle(raw_crash) == (
                REJECT,
                "is_firefox_esr_unsupported_windows",
                25,
            )

        # If it returns CONTINUE, then it will trigger another rule
        with randommock(0.20):
            assert throttler.throttle(raw_crash) == (ACCEPT, "is_alpha_beta_esr", 100)

    @pytest.mark.parametrize("channel", ["aurora", "beta", "esr"])
    def test_is_alpha_beta_esr(self, throttler, channel):
        raw_crash = {"ProductName": "Test", "ReleaseChannel": channel}
        assert throttler.throttle(raw_crash) == (ACCEPT, "is_alpha_beta_esr", 100)

    @pytest.mark.parametrize("channel", ["nightly", "nightlyfoo"])
    def test_is_nightly(self, throttler, channel):
        raw_crash = {"ProductName": "Test", "ReleaseChannel": channel}
        assert throttler.throttle(raw_crash) == (ACCEPT, "is_nightly", 100)

    def test_is_firefox(self, throttler, randommock):
        with randommock(0.09):
            raw_crash = {"ProductName": "Firefox", "ReleaseChannel": "release"}
            assert throttler.throttle(raw_crash) == (ACCEPT, "is_firefox_desktop", 10)

        with randommock(0.9):
            raw_crash = {"ProductName": "Firefox", "ReleaseChannel": "release"}
            assert throttler.throttle(raw_crash) == (REJECT, "is_firefox_desktop", 10)

    def test_is_nothing(self, throttler):
        # None of the rules will match an empty crash
        raw_crash = {}
        assert throttler.throttle(raw_crash) == (ACCEPT, "accept_everything", 100)
