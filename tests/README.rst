============
Tests README
============

In this directory are all the tests for Antenna. Each subdirectory holds a
different test system. Consult the README in the subdirectory for details
on setting up and running those tests.


Subdirectories
==============

**tests/data/**

    Data to make it easier to test a local instance.

**tests/unittest/**

    These are written in Python, use py.test as the test runner and are run
    during normal development to unit test the code in Antenna.

    These are run in a docker container using the ``make test`` rule.
