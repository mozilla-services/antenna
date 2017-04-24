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


Running tests against Antenna in -dev
=====================================

Set up a ``.env`` file with the correct configuration for the environment
you're testing against.

Run::

    ANTENNA_ENV=my.env make test-system


You can run specific tests or groups of tests or with different py.test
options::

    ANTENNA_ENV=my.env make test-system-shell


Make sure to set ``ANTENNA_ENV`` as the path to the env file with the
following items defined in it:

``POSTURL``
    The full URL to post to.

    Example: ``POSTURL=http://localhost:8000/submit``

``NONGINX``
    Set ``NONGINX=1`` if you're running against a local dev environment
    that isn't using Nginx. This will skip tests that require Nginx.

``CRASHSTORAGE_ACCESS_KEY`` and ``CRASHSTORAGE_SECRET_ACCESS_KEY``
    The systemtest will use these if supplied to access AWS S3. There
    are other ways to provide credentials, too. See the Boto3 documentation
    for details:

    http://boto3.readthedocs.io/en/latest/guide/configuration.html

    The credentials supplied must have the following permission:

    * ``s3:ListBucket``

``CRASHSTORAGE_ENDPOINT_URL``
    If you're using a fake s3 (for example, moto), you need to define this.

``CRASHSTORAGE_REGION``
    The regeion you're using. Defaults to ``us-west-2``.

``CRASHSTORAGE_BUCKET_NAME``
    The name of the bucket that Antenna is saving to.
