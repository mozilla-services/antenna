===========
Development
===========


Testing
=======

We're using py.test_ for a test harness and test discovery.

We use WebTest_ for testing the WSGI application and HTTP requests.

Files holding testing data should go in the ``tests/data/`` directory.

We have the following helpful fixtures:

``testapp``
    Provides a WebTest test application for testing HTTP requests.

    For details on this, see the `WebTest docs
    <http://webtest.pythonpaste.org/en/latest/index.html>`_.

``datadir``
    Provides the path to the directory holding test data.


.. _WebTest: http://webtest.pythonpaste.org/en/latest/index.html
.. _py.test: http://pytest.org/
