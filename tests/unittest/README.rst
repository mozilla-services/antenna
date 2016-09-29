===============
Unittest README
===============

These test the Antenna code. We use the py.test test runner.

Contents of this directory::

    conftest.py -- holds py.test fixtures
    data/       -- data used by these tests
    test_*.py   -- a test file


Run these tests from the repository root using::

    make test


To run a single test or group of tests or with different options, do::

    docker-compose run web py.test [ARGS]


You can also do::

    docker-compose run web bash


And then you get a bash shell in the docker container where you can more easily
do test runs and debugging.
