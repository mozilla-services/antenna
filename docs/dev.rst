================
Developer errata
================

Code
====

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

If you're not familiar with Docker and docker-compose, it's worth reading up on.


Documentation
=============

Documentation is compiled with Sphinx_ and is available on ReadTheDocs.
API is automatically extracted from docstrings in the code.

To build the docs, run this:

.. code-block:: shell

    $ make docs


.. _Sphinx: http://www.sphinx-doc.org/en/stable/


Testing
=======

To run the tests, run this:

.. code-block:: shell

   $ make test


Tests go in ``tests/``. Data required by tests goes in ``tests/data/``.

If you need to run specific tests or pass in different arguments, you can run
bash in the base container and then run ``py.test`` with whatever args you
want. For example:

.. code-block:: shell

   $ make shell
   app@...$ py.test

   <pytest output>

   app@...$ py.test tests/unittest/test_crashstorage.py


We're using py.test_ for a test harness and test discovery.

.. _py.test: http://pytest.org/
