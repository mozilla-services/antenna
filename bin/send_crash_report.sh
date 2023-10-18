#!/bin/bash

# Sends a fake crash report to the host specified in $HOST
# defaulting to http://localhost:8000 .

set -euo pipefail

URL="${1:-http://localhost:8000}/submit"

curl -v -H 'Host: crash-reports' \
     -F 'uuid=a448814e-16dd-45fb-b7dd-b0b522161010' \
     -F 'ProductName=Firefox' \
     -F 'Version=1' \
     -F upload_file_minidump=@tests/data/fakecrash.dump \
     "$URL"
