==================
All about breakpad
==================

Links about breakpad
====================

Breakpad project home page:
    https://chromium.googlesource.com/breakpad/breakpad

Firefox Breakpad page:
    https://wiki.mozilla.org/Breakpad

    Note: A lot of this is out of date.

Socorro docs:
    http://socorro.readthedocs.io/en/latest/

    Notes on testing collector and processor:
    http://socorro.readthedocs.io/en/latest/configuring-socorro.html#test-collection-and-processing


Where do reports come from?
===========================

From Ted:

    We use different code to submit crash reports on all 4 major platforms we ship
    Firefox on: Windows, OS X, Linux, Android, and we also have a separate path for
    submitting crash reports from within Firefox (for crashes in content processes,
    plugin processes, and used when you click an unsubmitted report in
    about:crashes).

    For all the desktop platforms, the crashreporter client (the window that says
    "We're Sorry") is some C++ code that lives here:
    https://dxr.mozilla.org/mozilla-central/source/toolkit/crashreporter/client/

    For Windows the submission code in the client is here:
    https://dxr.mozilla.org/mozilla-central/rev/8d0aadfe7da782d415363880008b4ca027686137/toolkit/crashreporter/client/crashreporter_win.cpp#391

    which calls into Breakpad code here:
    https://dxr.mozilla.org/mozilla-central/rev/8d0aadfe7da782d415363880008b4ca027686137/toolkit/crashreporter/google-breakpad/src/common/windows/http_upload.cc#65

    which uses WinINet APIs to do most of the hard work. If you look near the
    bottom of that function you can see that it does require a HTTP 200 response
    code for success, but it doesn't look like it cares about the response
    content-type.

    For OS X the submission code is here:
    https://dxr.mozilla.org/mozilla-central/rev/8d0aadfe7da782d415363880008b4ca027686137/toolkit/crashreporter/client/crashreporter_osx.mm#555

    It uses Cocoa APIs to do the real work. It also checks for HTTP status 200 for success.

    For Linux the submission code is here:
    https://dxr.mozilla.org/mozilla-central/rev/8d0aadfe7da782d415363880008b4ca027686137/toolkit/crashreporter/client/crashreporter_gtk_common.cpp#190

    which calls into Breakpad code here:
    https://dxr.mozilla.org/mozilla-central/rev/8d0aadfe7da782d415363880008b4ca027686137/toolkit/crashreporter/google-breakpad/src/common/linux/http_upload.cc#57

    which calls into libcurl to do the work. It's a little hard for me to read,
    but it sets CURLOPT_FAILONERROR, which says it will only fail if the server
    returns a HTTP response code of 400 or higher, I believe.

    For Android the submission code is here:
    https://dxr.mozilla.org/mozilla-central/rev/8d0aadfe7da782d415363880008b4ca027686137/mobile/android/base/java/org/mozilla/gecko/CrashReporter.java#356

    which uses Java APIs. The Android client *does* gzip-compress the request
    body, and it also looks like it checks for HTTP 200
    (HttpURLConnection.HTTP_OK).

    For the in-browser case, the submission code is here:
    https://dxr.mozilla.org/mozilla-central/rev/8d0aadfe7da782d415363880008b4ca027686137/toolkit/crashreporter/CrashSubmit.jsm#253

    It uses XMLHttpRequest to submit, and it checks for HTTP status 200. I do
    note that it uses `responseText` on the XHR, so I'd have to read the XHR
    spec to see if that would break if the content-type of the response changed.


How do reports get to the collector?
====================================

Breakpad reports are submitted to a collector over HTTP.

Things to know about the HTTP POST request:

1. Incoming reports can be gzip compressed.

   This is particularly important for mobile.

2. The entire crash report and metadata is in the request body.

   Note that some of the information is duplicated in querystring variables to
   make logging and debugging easier.

3. HTTP POST request body is multi-part form data.

4. HTTP POST request body has previously had problems with null bytes and
   non-utf-8 characters. They've taken great pains to make sure it contains
   correct utf-8 characters.

   Still a good idea to do a pass on removing null bytes.

5. Content-length for HTTP POST request.

   TODO: Go through all the existing collector code to see if it *always* uses a
   Content-Length to determine the end of the data.

6. Crash reports can contain instructions on throttling.

   Crash report can contain::

     Throttleable=0

   If that's there and 0, then it should skip the throttler and be accepted,
   saved and processed.

     https://dxr.mozilla.org/mozilla-central/source/toolkit/crashreporter/CrashSubmit.jsm#282

7. Crash reports can contain a crash id.

   Crash report can contain::

     crash_id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

   We siphon crashes from our prod environment to our dev environment. We want
   these crash reports to end up with the same crash id. Thus it's possible for
   an incoming crash to have a crash id in the data.

   If it does have a crash id, we should use that.


Things to know about the HTTP POST response:

1. The HTTP POST response status code should be HTTP 200 if everything was fine.

2. Content-type for HTTP POST response can be anything, but ``text/plain`` is
   probably prudent.

3. HTTP POST response body should look like this::

     CrashID=bp-28a40956-d19e-48ff-a2ee-19a932160525


.. _testing-breakpad-crash-reporting:

Testing breakpad crash reporting
================================

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
