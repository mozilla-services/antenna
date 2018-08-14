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


ACCEPT = 0   # save and process
DEFER = 1    # save but don't process
REJECT = 2   # throw the crash away

RESULT_TO_TEXT = {
    0: 'ACCEPT',
    1: 'DEFER',
    2: 'REJECT'
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
        """Go through rule set to ACCEPT, REJECT or DEFER

        :arg dict raw_crash: the crash to throttle

        :returns tuple: ``(result, rule_name, percentage)``

        """
        for rule in self.rule_set:
            match = rule.match(self, raw_crash)

            if match:
                if rule.percentage is None:
                    return REJECT, rule.rule_name, None

                if rule.percentage == 100 or (random.random() * 100.0) <= rule.percentage:  # nosec
                    response = ACCEPT
                else:
                    response = DEFER
                return response, rule.rule_name, rule.percentage

        # None of the rules matched, so we defer
        return DEFER, 'NO_MATCH', 0


class Rule:
    """Defines a single rule"""
    RULE_NAME_RE = re.compile(r'^[a-z0-9_]+$', re.I)

    def __init__(self, rule_name, key, condition, percentage):
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

        :arg int percentage: The percentage of crashes that match the condition
            to accept and process.

        """
        self.rule_name = rule_name
        self.key = key
        if not callable(condition):
            raise ValueError('condition %r is not callable' % condition)
        self.condition = condition
        self.percentage = percentage

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


def match_firefox_pre_57(throttler, data):
    """Matches crashes for Firefox before 57

    Bug #1433316.

    """
    product = data.get('ProductName', '')
    version = data.get('Version', '')

    if not (product and version):
        return False

    try:
        major_version = int(version.split('.')[0])
    except ValueError:
        return False

    return (
        product == 'Firefox' and
        major_version < 57
    )


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
    'Thunderbird',
    'SeaMonkey'
]


#: Rule set to accept all incoming crashes
ACCEPT_ALL = [
    # Accept everything
    Rule('accept_everything', '*', always_match, 100)
]


#: Ruleset for Mozilla's crash collector
MOZILLA_RULES = [
    # Reject browser side of all multi-submission hang crashes
    Rule(
        rule_name='has_hangid_and_browser',
        key='*',
        condition=(
            lambda throttler, d: 'HangID' in d and d.get('ProcessType', 'browser') == 'browser'
        ),
        percentage=None
    ),

    # Reject infobar=true crashes for certain versions of Firefox desktop
    Rule(
        rule_name='infobar_is_true',
        key='*',
        condition=match_infobar_true,
        percentage=None
    ),

    # Reject all unsupported products; this does nothing if the list of
    # supported products is empty
    Rule(
        rule_name='unsupported_product',
        key='*',
        condition=match_unsupported_product,
        percentage=None
    ),

    # 100% of crashes that have a comment
    Rule(
        rule_name='has_comments',
        key='Comments',
        condition=always_match,
        percentage=100
    ),

    # 100% of crashes that have an email address with at least an @
    Rule(
        rule_name='has_email',
        key='Email',
        condition=lambda throttler, x: x and '@' in x,
        percentage=100
    ),

    # 100% of all ReleaseChannel=aurora, beta, esr channels
    Rule(
        rule_name='is_alpha_beta_esr',
        key='ReleaseChannel',
        condition=lambda throttler, x: x in ('aurora', 'beta', 'esr'),
        percentage=100
    ),

    # 100% of all ReleaseChannel=nightly
    Rule(
        rule_name='is_nightly',
        key='ReleaseChannel',
        condition=lambda throttler, x: x.startswith('nightly'),
        percentage=100
    ),

    # 20% of Firefox 56 and earlier
    Rule(
        rule_name='firefox_pre_57',
        key='*',
        condition=match_firefox_pre_57,
        percentage=20
    ),

    # 10% of ProductName=Firefox
    Rule(
        rule_name='is_firefox_desktop',
        key='ProductName',
        condition=lambda throttler, x: x == 'Firefox',
        percentage=10
    ),

    # 100% of ProductName=Fennec
    Rule(
        rule_name='is_fennec',
        key='ProductName',
        condition=lambda throttler, x: x == 'Fennec',
        percentage=100
    ),

    # 100% of all Version=alpha, beta or special
    Rule(
        rule_name='is_version_alpha_beta_special',
        key='Version',
        condition=lambda throttler, x: '.' in x and x[-1].isalpha(),
        percentage=100
    ),

    # 100% of ProductName=Thunderbird & SeaMonkey
    Rule(
        rule_name='is_thunderbird_seamonkey',
        key='ProductName',
        condition=lambda throttler, x: x and x[0] in 'TSC',
        percentage=100
    ),

    # Reject everything else
]
