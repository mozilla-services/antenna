============
Contributing
============

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
    # file, You can obtain one at http://mozilla.org/MPL/2.0/.


PEP8 is nice. To lint your code, do:

.. code-block:: shell

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
<http://www.sphinx-doc.org/en/stable/>`_ and is available on ReadTheDocs. API is
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
bash in the base container and then run ``py.test`` with whatever args you want.
For example:

.. code-block:: shell

   $ make shell
   app@...$ py.test

   <pytest output>

   app@...$ py.test tests/unittest/test_crashstorage.py


We're using `py.test <https://pytest.org/>`_ for a test harness and test
discovery.
