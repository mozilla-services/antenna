======
README
======

These test the Antenna code. We use the pytest test runner.

Contents of this directory::

    data/       -- holds test data
    conftest.py -- holds pytest fixtures
    test_*.py   -- a test file


Run these tests from the repository root using::

    $ just test


To run a single test or group of tests or with different options, do::

    $ just test tests/test_some_file.py


Or to get a bash shell in the docker container where you can more easily
do test runs and debugging::

    $ just test-shell
    app@test:/app$ tests/test_some_file.py
