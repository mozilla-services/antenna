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

   $ py.test


Tests go in ``tests/``. Data required by tests goes in ``tests/data/``.

We're using py.test_ for a test harness and test discovery. We use WebTest_ for
testing the WSGI application and HTTP requests.

.. _WebTest: http://webtest.pythonpaste.org/en/latest/index.html
.. _py.test: http://pytest.org/
