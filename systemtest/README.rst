=================
Systemtest README
=================

These test Antenna as a whole and are designed to be run against a running
Antenna instance. We use the pytest test runner.

Contents of this directory::

    conftest.py  -- holds pytest fixtures
    test_*.py    -- test files
    test_env.sh  -- test runner shell script to run against an environment


Running tests
=============

In a terminal, run::

    $ just setup
    $ just shell ./systemtest/test_env.sh ENV


Additional arguments will be passed through to pytest. For example::

    $ just shell ./systemtest/test_env.sh ENV -- test_dockerflow.py


If you're running against ``local``, you'll need to be running antenna
in another terminal::

    $ just run


CI
--

These tests are run in CI without nginx.


Rules of systemtest
===================

1. Thou shalt not import anything from ``antenna``.

2. If the test requires nginx (for example, testing whether crash reports
   > 20mb are rejected which is configured in nginx), then use the nginx
   pytest fixture to optionally skip::

      def test_my_nginx_test(nginx):
          if not nginx:
              pytest.skip("test requires nginx")

3. Tests can check GCS to see if a file exists by listing objects, but
   cannot get the file.

4. Tests won't check Pub/Sub at all unless they're using the Pub/Sub
   emulator.
