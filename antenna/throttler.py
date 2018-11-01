# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Defines the throttler for the breakpad handler for Antenna.

The throttler lets you define rules for which crashes to accept (save and
process), defer (save, but not process), and reject.

"""

import importlib
import logging
import random
import re

from everett.component import ConfigOptions, RequiredConfigMixin


logger = logging.getLogger(__name__)


ACCEPT = 0      # save and process
DEFER = 1       # save but don't process
REJECT = 2      # throw the crash away
FAKEACCEPT = 3  # return crashid as if we accepted, but throw away--USE CAUTION!

RESULT_TO_TEXT = {
    0: 'ACCEPT',
    1: 'DEFER',
    2: 'REJECT',
    3: 'FAKEACCEPT'
}


def parse_attribute(val):
    module, attribute_name = val.rsplit('.', 1)
    module = importlib.import_module(module)
    try:
        return getattr(module, attribute_name)
    except AttributeError:
        raise ValueError(
            '%s is not a valid attribute of %s' %
            (attribute_name, module)
        )


class Throttler(RequiredConfigMixin):
    """Accepts/rejects incoming crashes based on specified rule set

    The throttler can throttle incoming crashes using the content of the crash.
    To throttle, you set up a rule set which is a list of ``Rule`` instances.
    That goes in a Python module which is loaded at run time.

    If you don't want to throttle anything, use this::

        THROTTLE_RULES=antenna.throttler.ACCEPT_ALL

    If you want to support all products, use this::

        PRODUCTS=antenna.throttler.ALL_PRODUCTS

    To set up a rule set, put it in a Python file and define the rule set
    there. For example, you could have file ``myruleset.py`` with this in it::

        from antenna.throttler import Rule

        rules = [
            Rule('ProductName', 'Firefox', 100),
            # ...
        ]

    then set ``THROTTLE_RULES`` to the path for that. For example, depending
    on the current working directory and ``PYTHONPATH``, the above could be::

        THROTTLE_RULES=myruleset.rules


    FIXME(willkg): Flesh this out.

    """
    required_config = ConfigOptions()
    required_config.add_option(
        'throttle_rules',
        default='antenna.throttler.MOZILLA_RULES',
        doc='Python dotted path to ruleset',
        parser=parse_attribute
    )
    required_config.add_option(
        'products',
        default='antenna.throttler.MOZILLA_PRODUCTS',
        doc='Python dotted path to list of supported products',
        parser=parse_attribute
    )

    def __init__(self, config):
        self.config = config.with_options(self)
        self.rule_set = self.config('throttle_rules')

    def throttle(self, raw_crash):
        """Go through rule set to ACCEPT, DEFER, or REJECT

        :arg dict raw_crash: the crash to throttle

        :returns tuple: ``(result, rule_name, percentage)``

        """
        for rule in self.rule_set:
            match = rule.match(self, raw_crash)

            if match:
                if rule.result in (ACCEPT, DEFER, REJECT, FAKEACCEPT):
                    return rule.result, rule.rule_name, 100

                if (random.random() * 100.0) <= rule.result[0]:  # nosec
                    response = rule.result[1]
                else:
                    response = rule.result[2]
                return response, rule.rule_name, rule.result[0]

        # None of the rules matched, so we defer
        return REJECT, 'NO_MATCH', 0


class Rule:
    """Defines a single rule"""
    RULE_NAME_RE = re.compile(r'^[a-z0-9_]+$', re.I)

    def __init__(self, rule_name, key, condition, result):
        """Creates a Rule

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
            raise ValueError('condition %r is not callable' % condition)
        self.condition = condition
        self.result = result

        if not self.RULE_NAME_RE.match(self.rule_name):
            raise ValueError('%r is not a valid rule name' % self.rule_name)

    def __repr__(self):
        return self.rule_name

    def match(self, throttler, crash):
        if self.key == '*':
            return self.condition(throttler, crash)

        if self.key in crash:
            return self.condition(throttler, crash[self.key])

        return False


def always_match(throttler, crash):
    """Rule condition that always returns true"""
    return True


def match_infobar_true(throttler, data):
    """Matches crashes we need to filter out due to infobar bug

    Bug #1425949.

    """
    product = data.get('ProductName', '')
    infobar = data.get('SubmittedFromInfobar', '')
    version = data.get('Version', '')
    buildid = data.get('BuildID', '')

    if not (product and infobar and version and buildid):
        return False

    return (
        product == 'Firefox' and
        infobar == 'true' and
        version.startswith(('52.', '53.', '54.', '55.', '56.', '57.', '58.', '59.')) and
        buildid < '20171226'
    )


def match_b2g(throttler, data):
    is_b2g = (
        'B2G' not in throttler.config('products') and
        data.get('ProductName', '').lower() == 'b2g'
    )
    if is_b2g:
        logger.info('ProductName B2G: fake accept')
        return True
    return False


def match_unsupported_product(throttler, data):
    is_not_supported = (
        throttler.config('products') and
        data.get('ProductName') not in throttler.config('products')
    )

    if is_not_supported:
        logger.info('ProductName rejected: %r' % data.get('ProductName'))
        return True
    return False


#: This accepts crash reports for all products
ALL_PRODUCTS = []


#: List of supported products; these have to match the ProductName of the
#: incoming crash report
MOZILLA_PRODUCTS = [
    'Firefox',
    'Fennec',
    'FirefoxReality',
    'Focus',
    'GeckoViewExample',
    'ReferenceBrowser',
    'Thunderbird',
    'SeaMonkey',
]


#: Rule set to accept all incoming crashes
ACCEPT_ALL = [
    # Accept everything
    Rule('accept_everything', '*', always_match, ACCEPT)
]


#: Ruleset for Mozilla's crash collector throttler
MOZILLA_RULES = [
    # Reject browser side of all multi-submission hang crashes
    Rule(
        rule_name='has_hangid_and_browser',
        key='*',
        condition=(
            lambda throttler, d: 'HangID' in d and d.get('ProcessType', 'browser') == 'browser'
        ),
        result=REJECT
    ),

    # Reject infobar=true crashes for certain versions of Firefox desktop
    Rule(
        rule_name='infobar_is_true',
        key='*',
        condition=match_infobar_true,
        result=REJECT
    ),

    # "Fake accept" B2G crash reports because B2G doesn't handle rejection
    # well and will retry ad infinitum
    Rule(
        rule_name='b2g',
        key='*',
        condition=match_b2g,
        result=FAKEACCEPT
    ),

    # Reject crash reports for unsupported products; this does nothing if the
    # list of supported products is empty
    Rule(
        rule_name='unsupported_product',
        key='*',
        condition=match_unsupported_product,
        result=REJECT
    ),

    # Accept crash reports submitted through about:crashes
    Rule(
        rule_name='throttleable_0',
        key='Throttleable',
        condition=lambda throttler, x: x == '0',
        result=ACCEPT
    ),

    # Accept crash reports that have a comment
    Rule(
        rule_name='has_comments',
        key='Comments',
        condition=always_match,
        result=ACCEPT
    ),

    # Accept crash reports that have an email address with at least an @
    Rule(
        rule_name='has_email',
        key='Email',
        condition=lambda throttler, x: x and '@' in x,
        result=ACCEPT
    ),

    # Accept crash reports in ReleaseChannel=aurora, beta, esr channels
    Rule(
        rule_name='is_alpha_beta_esr',
        key='ReleaseChannel',
        condition=lambda throttler, x: x in ('aurora', 'beta', 'esr'),
        result=ACCEPT
    ),

    # Accept crash reports in ReleaseChannel=nightly
    Rule(
        rule_name='is_nightly',
        key='ReleaseChannel',
        condition=lambda throttler, x: x.startswith('nightly'),
        result=ACCEPT
    ),

    # Accept 10%, reject 90% of Firefox desktop release channel
    Rule(
        rule_name='is_firefox_desktop',
        key='*',
        condition=lambda throttler, data: (
            data.get('ProductName', '') == 'Firefox' and
            data.get('ReleaseChannel', '') == 'release'
        ),
        result=(10, ACCEPT, REJECT)
    ),

    # Accept everything else
    Rule(
        rule_name='accept_everything',
        key='*',
        condition=always_match,
        result=ACCEPT
    )
]
