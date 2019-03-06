=================
Systemtest README
=================

These test Antenna as a whole and are designed to be run against a running
Antenna instance. We use the py.test test runner.

Contents of this directory::

    conftest.py  -- holds py.test fixtures
    test_*.py    -- a test file
    run_tests.sh -- test runner shell script



Running tests against locally running Antenna
=============================================

In a terminal, run::

    make run


to run Antenna.

Then in a separate terminal, run these tests from the repository root::

    make systemtest


If you want to run individual tests, or use different py.test options, do::

    make systemtest-shell


This gives you a bash shell in the docker container where you can more easily
run system tests and debugging.

Relevant configuration:

``NONGINX``
    Set ``NONGINX=1`` if you're running against a local dev environment
    that isn't using Nginx. This will skip tests that require Nginx.


Rules of systemtest
===================

1. Thou shalt not import anything from ``antenna``.

2. If the test requires nginx (for example, testing whether crash reports
   > 20mb are rejected which is configured in nginx), then add this
   decorator::

      @pytest.mark.skipif(
          bool(os.environ.get('NONGINX')),
          reason=(
              'Requires nginx which you probably do not have running '
              'via localhost'
          ))

3. Tests can check S3 to see if a file exists by listing objects, but
   cannot get the file.

4. Tests won't check Pub/Sub at all unless they're using the Pub/Sub
   emulator.
