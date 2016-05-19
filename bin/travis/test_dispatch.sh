#!/bin/bash

# Used by the travis scaffolding to dispatch specified "test runs".
#
# Usage: bin/travis/test_dispatch.sh SUITE

SUITE=${1:-all}

case $SUITE in
    lint )
        flake8 antenna tests
        ;;

    tests )
        PYTHONPATH=. py.test
        ;;

    * )
        echo "Unknown test suite $SUITE."
        exit 1
esac
