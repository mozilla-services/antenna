=================
Systemtest README
=================

These test Antenna as a whole and are designed to be run against a running
Antenna instance. We use the py.test test runner.

Contents of this directory::

    conftest.py -- holds py.test fixtures
    test_*.py   -- a test file


Run these tests from the repository root using::

    make test-system


To run a single test or group of tests or with different options, do::

    make test-system-shell


This gives you a bash shell in the docker container where you can more easily
run system tests and debugging.
