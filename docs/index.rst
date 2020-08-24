====================
Socorro Antenna docs
====================

Collector for the `Socorro crash ingestion pipeline
<https://socorro.readthedocs.io/>`_ that supports `breakpad-style crash reports
<https://chromium.googlesource.com/breakpad/breakpad>`_.

Uses Python 3, `Gunicorn <https://gunicorn.org/>`_, `gevent
<https://www.gevent.org/>`_, `Falcon <https://falconframework.org/>`_ and some
other things.

* Free software: Mozilla Public License version 2.0
* Code: https://github.com/mozilla-services/antenna/
* Documentation: https://antenna.readthedocs.io/
* Bugs: `Report a bug <https://bugzilla.mozilla.org/enter_bug.cgi?format=__standard__&product=Socorro&component=Antenna>`_
* Community Participation Guidelines: `Guidelines <https://github.com/mozilla-services/antenna/blob/main/CODE_OF_CONDUCT.md>`_


Contents
========

.. toctree::
   :caption: Dev/Ops documentation
   :maxdepth: 2

   quickstart
   configuration
   deploy
   architecture

.. toctree::
   :caption: Project documentation

   dev
   spec_v1


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
