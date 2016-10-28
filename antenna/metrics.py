# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Defines a metrics system allowing you to collect metrics about your
code while running.

This system is designed similarly to the Python logging system where the
application configures a metrics client, but everything else can grab a metrics
interface whenever they want including at module load time.

To use in code::

    from antenna import metrics

    class Foo:
        def __init__(self):
            self.mymetrics = metrics.get_metrics(self)

        def whatever(self):
            self.mymetrics.incr('whatever')


That'll generate a statsd stat of ``<MODULE>.Foo.whatever`` where ``<MODULE>``
is whatever module that class is defined in.

"""

import contextlib
from functools import wraps
import logging
import re
import time

from datadog.dogstatsd import DogStatsd
from everett.component import ConfigOptions, RequiredConfigMixin


NOT_ALPHANUM_RE = re.compile(r'[^a-z0-9_\.]', re.I)


logger = logging.getLogger(__name__)


_metrics_impl = None


def _change_metrics(new_impl):
    global _metrics_impl
    _metrics_impl = new_impl


class LoggingMetrics:
    """Metrics implementation that logs the values"""
    def __init__(self, config):
        pass

    def _log(self, fun_name, stat, kwargs):
        logger.info('LoggingMetrics.%s: %s %s', fun_name, stat, kwargs)

    def incr(self, stat, **kwargs):
        self._log('incr', stat, kwargs)

    def gauge(self, stat, **kwargs):
        self._log('gauge', stat, kwargs)

    def timing(self, stat, **kwargs):
        self._log('timing', stat, kwargs)


class DogStatsdMetrics(RequiredConfigMixin):
    """Uses the datadog DogStatsd client for statsd pings"""
    required_config = ConfigOptions()
    required_config.add_option(
        'statsd_host',
        default='localhost',
        doc='Hostname for the statsd server'
    )
    required_config.add_option(
        'statsd_port',
        default='8125',
        doc='Port for the statsd server',
        parser=int
    )
    required_config.add_option(
        'statsd_namespace',
        default='',
        doc='Namespace for these metrics'
    )

    def __init__(self, config):
        self.config = config.with_options(self)

        self.host = self.config('statsd_host')
        self.port = self.config('statsd_port')
        self.namespace = self.config('statsd_namespace')

        self.client = self.get_client(self.host, self.port, self.namespace)
        logger.info('%s configured: %s:%s %s', self.__class__.__name__, self.host, self.port, self.namespace)

    def get_client(self, host, port, namespace):
        return DogStatsd(host=host, port=port, namespace=namespace)

    def incr(self, stat, value=1):
        self.client.increment(metric=stat, value=value)

    def gauge(self, stat, value):
        self.client.gauge(metric=stat, value=value)

    def timing(self, stat, value):
        self.client.timing(metric=stat, value=value)


def metrics_configure(metrics_class, config):
    """Instantiates and configures the metrics implementation"""
    _change_metrics(metrics_class(config))


class MetricsInterface:
    """Interface to the underlying client.

    This calls the functions on the global client. This makes it possible to
    have module-level interfaces.

    For example, at the top of your Python module, you could have this::

        from antenna import metrics

        mymetrics = metrics.get_metrics(__name__)


    If that Python module was imported with ``antenna.app``, then that'd be the
    first part of all stats emitted by that metrics interface instance.

    Then later, you could define a class and have it get a metrics in the
    init::

        class SomeClass:
            def __init__(self):
                self.mymetrics = metrics.get_metrics(self)


    Any use of ``self.mymetrics`` would emit stats that start with
    ``antenna.app.SomeClass``.

    You could use this with Everett component namespaces, too. For example::

        class SomeClass2(RequiredConfigMixin):
            # ...
            def __init__(self, config):
                self.config = config.with_options(self)
                self.mymetrics = metrics.get_metrics(self, extra=config.get_namespace())


    If that config was in the namespace ``FOO``, then you have
    ``antenna.app.SomeClass2.foo`` as the first part of all stats.

    """
    def __init__(self, name):
        """Creates a MetricsInterface

        :arg str name: Use alphanumeric characters and underscore and period.
            Anything else gets converted to a period. Sequences of periods get
            collapsed to a single period.

        """
        # Convert all bad characters to .
        name = NOT_ALPHANUM_RE.sub('.', name)
        # Collapse sequences of . to a single .
        while True:
            new_name = name.replace('..', '.')
            if new_name == name:
                break
            name = new_name
        # Remove . at beginning and end
        self.name = name.strip('.')

    def _full_stat(self, stat):
        return self.name + '.' + stat

    def incr(self, stat, value=1):
        """Increment a stat by value"""
        _metrics_impl.incr(self._full_stat(stat), value=value)

    def gauge(self, stat, value):
        """Set a gauge stat as value"""
        _metrics_impl.gauge(self._full_stat(stat), value=value)

    def timing(self, stat, value):
        """Send timing information

        Note: value is in ms.

        """
        _metrics_impl.timing(self._full_stat(stat), value=value)

    @contextlib.contextmanager
    def timer(self, stat):
        """Contextmanager for easily computing timings

        For example::

            mymetrics = get_metrics(__name__)

            def long_function():
                with mymetrics.timer('long_function'):
                    # perform some thing we want to keep metrics on
                    ...

        """
        start_time = time.time()
        yield
        delta = time.time() - start_time
        self.timing(stat, delta * 1000.0)

    def timer_decorator(self, stat):
        """Timer decorator for easily computing timings

        For example::

            mymetrics = get_metrics(__name__)

            @mymetrics.timer_decorator('long_function')
            def long_function():
                # perform some thing we want to keep metrics on
                ...

        """
        def _inner(fun):
            @wraps(fun)
            def _timer_decorator(*args, **kwargs):
                with self.timer(stat):
                    return fun(*args, **kwargs)
            return _timer_decorator
        return _inner


def get_metrics(thing, extra=''):
    """Return a MetricsInterface instance with specified name

    Note: This is not tied to an actual metrics implementation. The
    implementation is globally configured. This allows us to have module-level
    variables without having to worry about bootstrapping order.

    :arg class/instance/str thing: The name to use as a prefix. If this
        is a class, it uses the dotted Python path. If this is an instance,
        it uses the dotted Python path plus ``str(instance)``.

    :arg str extra: Any extra bits to add to the end of the key.

    """
    if not isinstance(thing, str):
        # If it's not a str, it's either a class or an instance. Handle
        # accordingly.
        if type(thing) == type:
            thing = '%s.%s' % (thing.__module__, thing.__name__)
        else:
            thing = '%s.%s' % (thing.__class__.__module__, thing.__class__.__name__)

    if extra:
        thing = '%s.%s' % (thing, extra)

    return MetricsInterface(thing)


class MetricsMock:
    """Mock for recording metrics events and testing them"""
    def __init__(self):
        self.records = []
        self._old_impl = None
        self.client = self

    def _add_record(self, fun_name, stat, kwargs):
        self.records.append((fun_name, stat, kwargs))

    def incr(self, stat, **kwargs):
        self._add_record('incr', stat, kwargs)

    def gauge(self, stat, **kwargs):
        self._add_record('gauge', stat, kwargs)

    def timing(self, stat, **kwargs):
        self._add_record('timing', stat, kwargs)

    def __enter__(self):
        self.records = []
        self._old_impl = _metrics_impl
        _change_metrics(self)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        _change_metrics(self._old_impl)
        self._old_impl = None

    def get_metrics(self):
        return self.records

    def filter_metrics(self, fun_name=None, stat=None, kwargs_contains=None):
        def match_fun_name(record_fun_name):
            return fun_name is None or fun_name == record_fun_name

        def match_stat(record_stat):
            return stat is None or stat == record_stat

        def match_kwargs(record_kwargs):
            NO_VALUE = object()
            if kwargs_contains is None:
                return True
            for stat, val in record_kwargs.items():
                if kwargs_contains.get(stat, NO_VALUE) != val:
                    return False
            return True

        return [
            record for record in self.get_metrics()
            if (match_fun_name(record[0]) and
                match_stat(record[1]) and
                match_kwargs(record[2]))
        ]

    def has_metric(self, fun_name=None, stat=None, kwargs_contains=None):
        return bool(
            self.filter_metrics(
                fun_name=fun_name,
                stat=stat,
                kwargs_contains=kwargs_contains
            )
        )

    def print_metrics(self):
        for record in self.get_metrics():
            print(record)
