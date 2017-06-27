====================
Socorro Antenna docs
====================

`Breakpad crash <https://chromium.googlesource.com/breakpad/breakpad>`_
collector web app that handles incoming crash reports and saves them
to AWS S3.

Uses Python 3, `Gunicorn <http://gunicorn.org/>`_, `gevent
<http://www.gevent.org/>`_, `Falcon <https://falconframework.org/>`_ and some
other things.

* Free software: Mozilla Public License version 2.0
* Code: https://github.com/mozilla-services/antenna/
* Documentation: https://antenna.readthedocs.io/


Contents
========

User docs:

.. toctree::
   :maxdepth: 2

   quickstart
   configuration
   deploy
   architecture
   breakpad_reporting


Project docs:

.. toctree::

   dev
   spec_v1


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
