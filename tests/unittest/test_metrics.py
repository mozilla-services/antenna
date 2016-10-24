# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from unittest.mock import patch

from everett.manager import ConfigManager

from antenna import metrics


class TestMetricsMock:
    """Verify the MetricsMock works as advertised"""
    def test_print_metrics(self, metricsmock):
        # NOTE(willkg): .print_metrics() prints to stdout and is mostly used
        # for debugging tests. So we're just going to run it and make sure it
        # doesn't throw errors.
        with metricsmock as mm:
            mymetrics = metrics.get_metrics('foobar')
            mymetrics.incr('key1')

            mm.print_metrics()

    def test_filter_metrics(self, metricsmock):
        with metricsmock as mm:
            mymetrics = metrics.get_metrics('foobar')
            mymetrics.incr('key1')

            # Test fun_name match
            key1_metrics = mm.filter_metrics(
                stat='foobar.key1',
                kwargs_contains={'count': 1}
            )
            assert len(key1_metrics) == 1

            key1_metrics = mm.filter_metrics(
                fun_name='incr',
                stat='foobar.key1',
                kwargs_contains={'count': 1}
            )
            assert len(key1_metrics) == 1

            key1_metrics = mm.filter_metrics(
                fun_name='timing',
                stat='foobar.key1',
                kwargs_contains={'delta': 1}
            )
            assert len(key1_metrics) == 0

            # Test key match
            key1_metrics = mm.filter_metrics(
                fun_name='incr',
                kwargs_contains={'count': 1}
            )
            assert len(key1_metrics) == 1

            key1_metrics = mm.filter_metrics(
                fun_name='incr',
                stat='foobar.key1',
                kwargs_contains={'count': 1}
            )
            assert len(key1_metrics) == 1

            key1_metrics = mm.filter_metrics(
                fun_name='incr',
                stat='foobar.key1',
                kwargs_contains={'count': 1}
            )
            assert len(key1_metrics) == 1

            key1_metrics = mm.filter_metrics(
                fun_name='incr',
                stat='foobar.key2',
                kwargs_contains={'count': 1}
            )
            assert len(key1_metrics) == 0

            # Test kwargs_contains
            key1_metrics = mm.filter_metrics(
                fun_name='incr',
                stat='foobar.key1',
            )
            assert len(key1_metrics) == 1

            key1_metrics = mm.filter_metrics(
                fun_name='incr',
                stat='foobar.key1',
                kwargs_contains={'count': 1}
            )
            assert len(key1_metrics) == 1

            key1_metrics = mm.filter_metrics(
                fun_name='incr',
                stat='foobar.key1',
                kwargs_contains={'count': 5}
            )
            assert len(key1_metrics) == 0

    def test_has_metric(self, metricsmock):
        # NOTE(willkg): .has_metric() is implemented using .filter_metrics() so
        # we can test that aggressively and just make sure the .has_metric()
        # wrapper works fine.
        #
        # If that ever changes, we should update this test.
        with metricsmock as mm:
            mymetrics = metrics.get_metrics('foobar')
            mymetrics.incr('key1')

            assert mm.has_metric(
                fun_name='incr',
                stat='foobar.key1',
                kwargs_contains={
                    'count': 1
                }
            )

            assert not mm.has_metric(
                fun_name='incr',
                stat='foobar.key1',
                kwargs_contains={
                    'count': 5
                }
            )


class TestLoggingMetrics:
    """Test LoggingMetrics works

    NOTE(willkg): We don't spend a lot of time on this because it's a debugging
    metrics class.

    """
    def test_basic(self, loggingmock):
        # Configure metrics with a LoggingMetrics, get a metrics thing and
        # then call .incr() and make sure it got logged.
        with loggingmock(['antenna']) as lm:
            metrics.metrics_configure(metrics.LoggingMetrics, ConfigManager.from_dict({}))
            mymetrics = metrics.get_metrics('foobar')
            mymetrics.incr('key1')

            assert lm.has_record(
                name='antenna.metrics',
                levelname='INFO',
                msg_contains=[
                    'LoggingMetrics.incr', 'key1'
                ]
            )


class TestMetricsInterface:
    """Verify MetricsInterface works"""
    def test_get_metrics(self):
        mymetrics = metrics.get_metrics('foobar')
        assert mymetrics.name == 'foobar'

    def test_get_metrics_class(self):
        class Foo:
            pass
        mymetrics = metrics.get_metrics(Foo)
        assert mymetrics.name == 'test_metrics.Foo'

    def test_get_metrics_instance(self):
        class Foo:
            pass
        mymetrics = metrics.get_metrics(Foo())
        assert mymetrics.name == 'test_metrics.Foo'

    def test_get_metrics_extra(self):
        mymetrics = metrics.get_metrics('foo', extra='bar')
        assert mymetrics.name == 'foo.bar'

    def test_get_metrics_bad_chars(self):
        mymetrics = metrics.get_metrics('ou812  : blah blah\n')
        assert mymetrics.name == 'ou812.blah.blah'

    def test_timer(self, loggingmock):
        with loggingmock(['antenna']) as lm:
            metrics.metrics_configure(metrics.LoggingMetrics, ConfigManager.from_dict({}))
            mymetrics = metrics.get_metrics('foobar')

            with patch.object(metrics.time, 'time', return_value=1477355330.0) as mock_time:
                with mymetrics.timer('key1'):
                    # Let 15 seconds pass in alternate reality time....
                    mock_time.return_value += 15

            assert lm.has_record(
                name='antenna.metrics',
                levelname='INFO',
                msg_contains=[
                    'LoggingMetrics.timing', 'foobar.key1', '\'delta\': 15000.0'
                ]
            )

    # FIXME(willkg): We should test .timer_decorator(), too, but it's trickier
    # because of the patching and it just turns around and uses .timer(), so
    # doesn't seem like it's worth the effort to do right now.


class TestDogStatsdMetrics:
    def test_incr(self):
        metrics.metrics_configure(metrics.DogStatsdMetrics, ConfigManager.from_dict({}))
        mymetrics = metrics.get_metrics('foobar')

        with patch.object(metrics._metrics_impl.client, 'increment') as mock_incr:
            mymetrics.incr('key1')
            mock_incr.assert_called_with(stat='foobar.key1', count=1)

    def test_timing(self):
        metrics.metrics_configure(metrics.DogStatsdMetrics, ConfigManager.from_dict({}))
        mymetrics = metrics.get_metrics('foobar')

        with patch.object(metrics._metrics_impl.client, 'timing') as mock_timing:
            mymetrics.timing('key1', 1000)
            mock_timing.assert_called_with(stat='foobar.key1', delta=1000)

    def test_gauge(self):
        metrics.metrics_configure(metrics.DogStatsdMetrics, ConfigManager.from_dict({}))
        mymetrics = metrics.get_metrics('foobar')

        with patch.object(metrics._metrics_impl.client, 'gauge') as mock_gauge:
            mymetrics.gauge('key1', 5)
            mock_gauge.assert_called_with(stat='foobar.key1', value=5)
