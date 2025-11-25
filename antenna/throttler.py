# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Defines the throttler for the breakpad handler for Antenna.

The throttler lets you define rules for which crashes to accept (save and
process), defer (save, but not process), and reject.

"""

import datetime
import importlib
import json
import logging
import random
import re

from everett.manager import Option


LOGGER = logging.getLogger(__name__)


ACCEPT = 0  # save and process
DEFER = 1  # save but don't process
REJECT = 2  # throw the crash away
FAKEACCEPT = 3  # return crashid as if we accepted, but throw away--USE CAUTION!
CONTINUE = 4  # continue through rules

RESULT_TO_TEXT = {0: "ACCEPT", 1: "DEFER", 2: "REJECT", 3: "FAKEACCEPT", 4: "CONTINUE"}


def safe_get(data, key, default=""):
    """Return a sanitized data[key].

    Throttle rule conditions operate on strings since strings are the predominant value
    type for crash report annotations.

    This forces the value to be a string. For example, `None` will become `"None"`.

    :return: string value

    """
    return str(data.get(key, default))


def parse_attribute(val):
    """Everett parser for module attributes."""
    module, attribute_name = val.rsplit(".", 1)
    module = importlib.import_module(module)
    try:
        return getattr(module, attribute_name)
    except AttributeError as exc:
        raise ValueError(
            f"{attribute_name} is not a valid attribute of {module}"
        ) from exc


class Throttler:
    """Accept or reject incoming crashes based on specified rule set.

    The throttler can throttle incoming crashes using the content of the crash.
    To throttle, you set up a rule set which is a list of ``Rule`` instances.
    That goes in a Python module which is loaded at run time.

    If you don't want to throttle anything, use this::

        BREAKPAD_THROTTLER_RULES=antenna.throttler.ACCEPT_ALL

    If you want to support all products, use this::

        BREAKPAD_THROTTLER_PRODUCTS=antenna.throttler.ALL_PRODUCTS

    To set up a rule set, put it in a Python file and define the rule set
    there. For example, you could have file ``myruleset.py`` with this in it::

        from antenna.throttler import Rule

        rules = [
            Rule('ProductName', 'Firefox', 100),
            # ...
        ]

    then set ``BREAKPAD_THROTTLER_RULES`` to the path for that. For example,
    depending on the current working directory and ``PYTHONPATH``, the above could be::

        BREAKPAD_THROTTLER_RULES=myruleset.rules

    """

    class Config:
        rules = Option(
            default="antenna.throttler.MOZILLA_RULES",
            doc="Python dotted path to ruleset",
            parser=parse_attribute,
        )
        products = Option(
            default="antenna.throttler.MOZILLA_PRODUCTS",
            doc="Python dotted path to list of supported products",
            parser=parse_attribute,
        )
        product_packagenames = Option(
            default="antenna.throttler.MOZILLA_PRODUCT_PACKAGENAMES",
            doc="Python dotted path to map of product -> list of supported packagenames",
            parser=parse_attribute,
        )

    def __init__(self, config):
        self.config = config.with_options(self)
        self.rule_set = self.config("rules")

    def throttle(self, raw_crash):
        """Throttle an incoming crash report.

        This goes through the rule set and returns one of ACCEPT, DEFER, or
        REJECT.

        :arg dict raw_crash: the crash to throttle

        :returns tuple: ``(result, rule_name, percentage)``

        """
        for rule in self.rule_set:
            match = rule.match(self, raw_crash)

            if match:
                if rule.result in (ACCEPT, DEFER, REJECT, FAKEACCEPT):
                    return rule.result, rule.rule_name, 100

                if (random.random() * 100.0) <= rule.result[0]:  # noqa: S311
                    response = rule.result[1]
                else:
                    response = rule.result[2]

                if response != CONTINUE:
                    return response, rule.rule_name, rule.result[0]

        # None of the rules matched, so we defer
        return REJECT, "NO_MATCH", 0


class Rule:
    """Defines a single rule."""

    RULE_NAME_RE = re.compile(r"^[a-z0-9_]+$", re.I)

    def __init__(self, rule_name, key, condition, result):
        """Create a Rule.

        :arg str rule_name: The friendly name for the rule. We use this for
            logging and statsd. Rule names must contain only alphanumeric
            characters and underscores.

        :arg str key: The key in the raw crash to look at. ``*`` to look at the
            whole crash.

        :arg varies condition: The condition that determines whether this rule
            matches.

            This can be a function that takes ``raw_crash[key]`` as a value
            or if the key is ``*``, the entire crash.

            This can be a boolean which will always return that value for all
            crashes.

            This can be any other kind of value which will be compared for equality
            with ``raw_crash[key]``.

        :arg varies result: Can be a single result like ``ACCEPT``, ``DEFER``, or
            ``REJECT`` in which case any crash report that triggers this rule gets
            this result.

            Can be a tuple of ``(number, LE_result, GT_result)``. A random number
            is computed. If it's less than or equal to the number, then the
            ``LE_result`` is the result. Otherwise the ``GT_result`` is the
            result.

            Example::

                (10, ACCEPT, REJECT)

                random number: 9 -> ACCEPT
                              10 -> ACCEPT
                              11 -> REJECT
                              72 -> REJECT


        """
        self.rule_name = rule_name
        self.key = key
        if not callable(condition):
            raise ValueError("condition %r is not callable" % condition)
        self.condition = condition
        self.result = result

        if not self.RULE_NAME_RE.match(self.rule_name):
            raise ValueError("%r is not a valid rule name" % self.rule_name)

    def __repr__(self):
        """Return programmer-friendly representation."""
        return self.rule_name

    def match(self, throttler, crash):
        """Apply this rule to the crash report."""
        if self.key == "*":
            return self.condition(throttler, crash)

        if self.key in crash:
            return self.condition(throttler, safe_get(crash, self.key))

        return False


def always_match(throttler, crash):
    """Rule condition that always returns true."""
    return True


def match_infobar_true(throttler, data):
    """Match crashes we need to filter out due to infobar bug.

    Bug #1426949.

    """
    product = safe_get(data, "ProductName")
    infobar = safe_get(data, "SubmittedFromInfobar")
    version = safe_get(data, "Version")
    buildid = safe_get(data, "BuildID")

    if not (product and infobar and version and buildid):
        return False

    return (
        product == "Firefox"
        and infobar == "true"
        and version.startswith(("52.", "53.", "54.", "55.", "56.", "57.", "58.", "59."))
        and buildid < "20171226"
    )


def match_b2g(throttler, data):
    """Match crash reports for B2G.

    Bug #1500243.

    """
    is_b2g = (
        "B2G" not in throttler.config("products")
        and safe_get(data, "ProductName").lower() == "b2g"
    )
    if is_b2g:
        LOGGER.info("ProductName B2G: fake accept")
        return True
    return False


def match_unsupported_product(throttler, data):
    """Match unsupported products."""
    products = throttler.config("products")
    product_name = safe_get(data, "ProductName")
    is_not_supported = products and product_name not in products

    if is_not_supported:
        LOGGER.info("ProductName rejected: %r", product_name)
        return True
    return False


def match_unsupported_android_packagename(throttler, data):
    """Match unsupported Android_PackageName values"""
    product_name = safe_get(data, "ProductName")

    packagenames = throttler.config("product_packagenames").get(product_name, [])
    packagename = safe_get(data, "Android_PackageName", default=None)

    is_not_supported = packagenames and packagename not in packagenames

    if is_not_supported:
        # NOTE(willkg): safe_get converts None to "None", so we need to test for that
        # here
        if packagename == "None":
            LOGGER.info(
                "Android_PackageName rejected: %s no Android_PackageName", product_name
            )
        else:
            LOGGER.info(
                "Android_PackageName rejected: %s %r", product_name, packagename
            )
        return True
    return False


BUILDID_RE = re.compile(r"^20\d{12}$")


def match_old_buildid(throttler, data):
    """Match build ids that are > 2 years old."""
    buildid = safe_get(data, "BuildID")
    if BUILDID_RE.match(buildid) is None:
        return False

    try:
        buildid_date = datetime.datetime.strptime(buildid[:8], "%Y%m%d")
    except ValueError:
        # If this buildid doesn't have a YYYYMMDD at the beginning, it's not a valid
        # buildid we want to look at
        return False

    now = datetime.datetime.now()
    return buildid_date < (now - datetime.timedelta(days=730))


WINDOWS_8_1_BUILD_NUMBER = 9600


def match_unsupported_windows(throttler, data):
    """Match Windows versions we don't support."""
    telemetry_environment = safe_get(data, "TelemetryEnvironment")
    if not telemetry_environment:
        return False

    try:
        telemetry_environment_data = json.loads(telemetry_environment)
    except (json.decoder.JSONDecodeError, UnicodeDecodeError):
        return False

    system_data = telemetry_environment_data.get("system")
    if not system_data or not isinstance(system_data, dict):
        return False

    os_data = system_data.get("os")
    if not os_data or not isinstance(os_data, dict):
        return False

    os_name = os_data.get("name")
    if not os_name or os_name != "Windows_NT":
        return False

    windows_build_number = os_data.get("windowsBuildNumber")
    if not windows_build_number or not isinstance(windows_build_number, int):
        return False

    # At this point, we should have a windowsBuildNumber with a valid value.
    return windows_build_number <= WINDOWS_8_1_BUILD_NUMBER


#: This accepts crash reports for all products
ALL_PRODUCTS = []


#: List of supported products; these have to match the ProductName of the
#: incoming crash report
MOZILLA_PRODUCTS = [
    "Fenix",
    "Firefox",
    "Firefox Enterprise",
    "Focus",
    "MozillaVPN",
    "ReferenceBrowser",
    "Thunderbird",
]


#: This accepts crash reports for all product packagenames
ALL_PRODUCT_PACKAGENAMES = {}


# Supported packagenames values; these have to match the Android_PackageName of the
# incoming crash report
MOZILLA_PRODUCT_PACKAGENAMES = {
    "Fenix": [
        "org.mozilla.firefox",
        "org.mozilla.firefox_beta",
        # This is the Nightly version of Firefox Android, not to be confused with
        # "org.mozilla.fenix.nightly", a retired version we no longer care about
        "org.mozilla.fenix",
    ],
    "Focus": [
        "org.mozilla.focus",
        "org.mozilla.focus.beta",
        "org.mozilla.focus.nightly",
        # This is the German version of Focus
        "org.mozilla.klar",
    ],
    "ReferenceBrowser": [
        "org.mozilla.reference.browser",
    ],
}


#: Rule set to accept all incoming crashes
ACCEPT_ALL = [
    # Accept everything
    Rule("accept_everything", "*", always_match, ACCEPT)
]


#: Ruleset for Mozilla's crash collector throttler
MOZILLA_RULES = [
    # If it's got an old build id, reject it now
    Rule(
        rule_name="has_old_buildid",
        key="*",
        condition=match_old_buildid,
        result=REJECT,
    ),
    # Reject browser side of all multi-submission hang crashes
    Rule(
        rule_name="has_hangid_and_browser",
        key="*",
        condition=(
            lambda throttler, data: (
                "HangID" in data
                and safe_get(data, "ProcessType", default="browser") == "browser"
            )
        ),
        result=REJECT,
    ),
    # Bug #1426949: Reject infobar=true crashes for certain versions of Firefox desktop
    Rule(
        rule_name="infobar_is_true",
        key="*",
        condition=match_infobar_true,
        result=REJECT,
    ),
    # Bug #1500243: "Fake accept" B2G crash reports because B2G doesn't handle rejection
    # well and will retry ad infinitum
    Rule(rule_name="b2g", key="*", condition=match_b2g, result=FAKEACCEPT),
    # Reject crash reports for unsupported products; this does nothing if the
    # list of supported products is empty
    Rule(
        rule_name="unsupported_product",
        key="*",
        condition=match_unsupported_product,
        result=REJECT,
    ),
    # bug #1819628: Reject crash reports for unsupported packagenames; this does nothing
    # if the dict of product -> packagename list is empty
    Rule(
        rule_name="unsupported_packagename",
        key="*",
        condition=match_unsupported_android_packagename,
        result=REJECT,
    ),
    # Accept crash reports submitted through about:crashes
    Rule(
        rule_name="throttleable_0",
        key="Throttleable",
        condition=lambda throttler, x: x == "0",
        result=ACCEPT,
    ),
    # Accept crash reports that have a comment
    Rule(
        rule_name="has_comments", key="Comments", condition=always_match, result=ACCEPT
    ),
    # Bug #1800531: Accept crash reports that have PHC
    Rule(rule_name="has_phc", key="PHCKind", condition=always_match, result=ACCEPT),
    # Bug #1547804: Accept crash reports from gpu crashes; we don't get many
    # and our sampling reduces that to a handful that's hard to do things with
    # Bug 1916751: Accept crash reports from rdd, plugin, utility and socket processes
    # for the same reasons as for Bug 1547804 above.
    Rule(
        rule_name="is_background",
        key="ProcessType",
        condition=lambda throttler, x: (
            x in {"gpu", "plugin", "rdd", "socket", "utility"}
        ),
        result=ACCEPT,
    ),
    # Bug #1624949: Throttle ipc_channel_error=ShutDownKill crash reports at
    # 10%--they're not really *crashes* and we get an awful lot of them
    Rule(
        rule_name="is_shutdownkill",
        key="ipc_channel_error",
        condition=lambda throttler, x: x == "ShutDownKill",
        result=(10, CONTINUE, REJECT),
    ),
    # Accept 25% crash reports from Firefox ESR Windows <= 8.1
    Rule(
        rule_name="is_firefox_esr_unsupported_windows",
        key="*",
        condition=(
            lambda throttler, data: (
                safe_get(data, "ProductName") == "Firefox"
                and safe_get(data, "ReleaseChannel") == "esr"
                and match_unsupported_windows(throttler, data)
            )
        ),
        result=(25, CONTINUE, REJECT),
    ),
    # Accept crash reports in ReleaseChannel=aurora, beta, esr channels
    Rule(
        rule_name="is_alpha_beta_esr",
        key="ReleaseChannel",
        condition=lambda throttler, x: x in ("aurora", "beta", "esr"),
        result=ACCEPT,
    ),
    # Accept crash reports in ReleaseChannel=nightly
    Rule(
        rule_name="is_nightly",
        key="ReleaseChannel",
        condition=lambda throttler, x: x.startswith("nightly"),
        result=ACCEPT,
    ),
    # Accept 10%, reject 90% of Firefox desktop release channel
    Rule(
        rule_name="is_firefox_desktop",
        key="*",
        condition=lambda throttler, data: (
            safe_get(data, "ProductName") == "Firefox"
            and safe_get(data, "ReleaseChannel") == "release"
        ),
        result=(10, ACCEPT, REJECT),
    ),
    # Accept everything else
    Rule(rule_name="accept_everything", key="*", condition=always_match, result=ACCEPT),
]
