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

    $ make shell
    app@xxx:/app$ cd systemtests
    app@xxx:/app/systemtests$ ./test_env.sh ENV


If you're running against ``localdev``, you'll need to be running antenna
in another terminal.


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
