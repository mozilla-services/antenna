============
Contributing
============

Code of Conduct
===============

This project and repository is governed by Mozilla's code of conduct and
etiquette guidelines. For more details please see the `CODE_OF_CONDUCT.md file
<https://github.com/mozilla-services/antenna/blob/main/CODE_OF_CONDUCT.md>`_.


Issues
======

Bugs and feature requests are tracked in `Bugzilla
<https://bugzilla.mozilla.org/>`_.

`Write up a new bug
<https://bugzilla.mozilla.org/enter_bug.cgi?format=__standard__&product=Socorro&component=Antenna>`_.

When writing up a bug, it helps to know the version of Antenna you're using.


Code conventions
================

All code files need to start with the MPLv2 header::

    # This Source Code Form is subject to the terms of the Mozilla Public
    # License, v. 2.0. If a copy of the MPL was not distributed with this
    # file, You can obtain one at https://mozilla.org/MPL/2.0/.


To lint your code, do:

.. code-block:: shell

    $ make lintfix
    $ make lint

If you hit issues, use ``# noqa``.


Docker
======

Everything runs in a Docker container. Thus Antenna requires fewer things to get
started and you're guaranteed to have the same setup as everyone else and it
solves some other problems, too.

If you're not familiar with `Docker <https://docs.docker.com/>`_ and
`docker-compose <https://docs.docker.com/compose/overview/>`_, it's worth
reading up on.


Documentation
=============

Documentation for Antenna is build with `Sphinx
<https://www.sphinx-doc.org/en/stable/>`_ and is available on ReadTheDocs. API is
automatically extracted from docstrings in the code.

To build the docs, run this:

.. code-block:: shell

    $ make docs


Testing
=======

To run the tests, run this:

.. code-block:: shell

   $ make test


Tests go in ``tests/``. Data required by tests goes in ``tests/data/``.

If you need to run specific tests or pass in different arguments, you can run
bash in the base container and then run ``pytest`` with whatever args you want.
For example:

.. code-block:: shell

   $ make shell
   app@...$ pytest

   <pytest output>

   app@...$ pytest tests/unittest/test_crashstorage.py


We're using `pytest <https://pytest.org/>`_ for a test harness and test
discovery.


.. _testing-breakpad-crash-reporting:

Testing crash reporting and collection
======================================

When working on Antenna, it helps to be able to send real live crashes to your
development instance. There are a few options:

1. Use Antenna's tools to send a fake crash:

   .. code-block:: bash

      $ make shell
      app@c392a11dbfec:/app$ python -m testlib.mini_poster --url URL

2. Use Firefox and set the ``MOZ_CRASHREPORTER_URL`` environment variable:

   https://developer.mozilla.org/en-US/docs/Environment_variables_affecting_crash_reporting


   * (Firefox >= 62) Use ``about:crashparent`` or ``about:crashcontent``.

   * (Firefox < 62) Then kill the Firefox process using the ``kill`` command.

     1. Run ``ps -aef | grep firefox``. That will list all the
        Firefox processes.

        Find the process id of the Firefox process you want to kill.

        * main process looks something like ``/usr/bin/firefox``
        * content process looks something like
          ``/usr/bin/firefox -contentproc -childID ...``

     2. The ``kill`` command lets you pass a signal to the process. By default, it
        passes ``SIGTERM`` which will kill the process in a way that doesn't
        launch the crash reporter.

        You want to kill the process in a way that *does* launch the crash
        reporter. I've had success with ``SIGABRT`` and ``SIGFPE``. For example:

        * ``kill -SIGABRT <PID>``
        * ``kill -SIGFPE <PID>``

        What works for you will depend on the operating system and version of
        Firefox you're using.


Capturing an HTTP POST payload for a crash report
=================================================

The HTTP POST payload for a crash report is sometimes handy to have. You can
capture it this way:

1. Run ``nc -l localhost 8000 > http_post.raw`` in one terminal.

2. Run ``MOZ_CRASHREPORTER_URL=http://localhost:8000/submit firefox`` in a
   second terminal.

3. Crash Firefox using one of the methods in
   :ref:`testing-breakpad-crash-reporting`.

4. The Firefox process will crash and the crash report dialog will pop up.
   Make sure to submit the crash, then click on "Quit Firefox" button.

   That will send the crash to ``nc`` which will pipe it to the file.

5. Wait 30 seconds, then close the crash dialog window.

   You should have a raw HTTP POST in ``http_post.raw``.
