=================
Systemtest README
=================

These test Antenna as a whole and are designed to be run against a running
Antenna instance. We use the py.test test runner.

Contents of this directory::

    conftest.py -- holds py.test fixtures
    test_*.py   -- a test file



Running tests against locally running Antenna
=============================================

Run these tests from the repository root using::

    make test-system


To run a single test or group of tests or with different options, do::

    make test-system-shell


This gives you a bash shell in the docker container where you can more easily
run system tests and debugging.


Running tests against Antenna in -dev
=====================================

Set up a ``.env`` file with the correct configuration for the environment
you're testing against.

Run::

    ANTENNA_ENV=my.env make test-system


You can run specific tests or groups of tests or with different py.test
options::

    ANTENNA_ENV=my.env make test-system-shell
