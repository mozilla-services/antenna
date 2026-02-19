# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

_default:
    @just --list

_env:
    #!/usr/bin/env sh
    if [ ! -f .env ]; then
      echo "Copying docker/config/.env.dist to .env..."
      cp docker/config/.env.dist .env
    fi

# Build docker images.
build *args='deploy-base fakesentry gcs-emulator statsd nginx': _env
    docker compose --progress plain build {{args}}

# Set up services.
setup: _env
    docker compose run --rm web shell ./bin/run_setup.sh

# Run the webapp and services.
run *args='--attach=web --attach=nginx --attach=fakesentry web nginx': _env
    docker compose up {{args}}

# Stop service containers.
stop *args:
    docker compose stop {{args}}

# Remove service containers and networks.
down *args:
    docker compose down {{args}}

# Open a shell in the web image.
shell *args='/bin/bash': _env
    docker compose run --rm --entrypoint= web {{args}}

# Open a shell in the test container.
test-shell *args='/bin/bash':
    docker compose run --rm --entrypoint= test {{args}}

# Remove build, test, and Python artifacts.
clean:
    # python related things
    -rm -rf build/
    -rm -rf dist/
    -rm -rf .eggs/
    find . -name '*.egg-info' -exec rm -rf {} +
    find . -name '*.egg' -exec rm -f {} +
    find . -name '*.pyc' -exec rm -f {} +
    find . -name '*.pyo' -exec rm -f {} +
    find . -name '__pycache__' -exec rm -rf {} +

    # docs files
    -rm -rf docs/_build/

# Lint code, or use --fix to reformat and apply auto-fixes for lint.
lint *args:
    docker compose run --rm --no-deps base shell ./bin/run_lint.sh {{args}}

# Run tests.
test *args:
    docker compose run --rm test shell ./bin/run_tests.sh {{args}}

# Generate Sphinx HTML documentation.
docs:
    docker compose run --rm --no-deps base shell ./bin/build_docs.sh

# Run uv inside the container
uv *args: _env
	docker compose run --rm --no-deps web shell uv {{args}}

# Check how far behind different server environments are from main tip.
service-status *args:
    docker compose run --rm --no-deps base shell service-status {{args}}
