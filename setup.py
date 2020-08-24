#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.


from setuptools import setup


def get_file(fn):
    with open(fn) as fp:
        return fp.read()


setup(
    name='antenna',
    version='0.1.0',
    description='Breakpad crash report collector',
    long_description=get_file('README.rst'),
    author='Socorro Team',
    author_email='socorro-dev@mozilla.com',
    url='https://github.com/mozilla-services/antenna',
    packages=[
        'antenna',
    ],
    package_dir={
        'antenna': 'antenna'
    },
    include_package_data=True,
    license='MPLv2',
    zip_safe=False,
    keywords='breakpad crash',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)',
        'Natural Language :: English',
        "Programming Language :: Python :: 3",
        'Programming Language :: Python :: 3.5',
    ],
)
