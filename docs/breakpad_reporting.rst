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

2. Content-type for HTTP POST response.

   TODO: Figure out whether we return a content-type now and if not, whether we
   should nix the content-type or whether we should set it to something. Maybe
   ``text/plain``? Maybe ``application/x-www-form-urlencoded``?

3. HTTP POST response body should look like this::

     CrashID=bp-28a40956-d19e-48ff-a2ee-19a932160525


Testing breakpad crash reporting
================================

When working on Antenna, it helps to be able to send real live crashes to your
development instance. There are a few options:

1. Use curl:

   http://socorro.readthedocs.io/en/latest/configuring-socorro.html#test-collection-and-processing

2. Use an addon:

   https://addons.mozilla.org/en-US/firefox/addon/crash-me-now-simple/

3. Set environment variables:

   https://developer.mozilla.org/en-US/docs/Environment_variables_affecting_crash_reporting

   Particularly ``MOZ_CRASHREPORTER_URL``.
