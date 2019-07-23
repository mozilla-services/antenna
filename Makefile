# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Include my.env and export it so variables set in there are available
# in Makefile.
include my.env
export

# Set these in the environment to override them. This is helpful for
# development if you have file ownership problems because the user
# in the container doesn't match the user on your host.
ANTENNA_UID ?= 10001
ANTENNA_GID ?= 10001

# Set this in the environment to force --no-cache docker builds.
DOCKER_BUILD_OPTS :=
ifeq (1, ${NOCACHE})
DOCKER_BUILD_OPTS := --no-cache
endif

DC := $(shell which docker-compose)

.PHONY: help
help: default

.PHONY: default
default:
	@echo "build            - build docker containers for dev"
	@echo "run              - docker-compose up the entire system for dev"
	@echo ""
	@echo "shell            - open a shell in the base container"
	@echo "clean            - remove all build, test, coverage and Python artifacts"
	@echo "lint             - check style with flake8"
	@echo "black            - run black on black-formatted Python files"
	@echo "test             - run unit tests"
	@echo "testshell        - open a shell in the test container"
	@echo "systemtest       - run system tests against a running Antenna instance"
	@echo "systemtest-shell - open a shell in the systemtest container"
	@echo "test-coverage    - run tests and generate coverage report in cover/"
	@echo "docs             - generate Sphinx HTML documentation, including API docs"
	@echo ""
	@echo "Adjust your my.env file to set configuration."

# Dev configuration steps
.docker-build:
	make build

my.env:
	@if [ ! -f my.env ]; \
	then \
	echo "Copying my.env.dist to my.env..."; \
	cp docker/config/my.env.dist my.env; \
	fi

.PHONY: build
build: my.env
	${DC} build ${DOCKER_BUILD_OPTS} --build-arg userid=${ANTENNA_UID} --build-arg groupid=${ANTENNA_GID} deploy-base
	touch .docker-build

.PHONY: run
run: my.env .docker-build
	${DC} up web

.PHONY: shell
shell: my.env .docker-build
	${DC} run web bash

.PHONY: my.env clean
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

	# test related things
	-rm -f .coverage

	# docs files
	-rm -rf docs/_build/

	# state files
	-rm .docker-build

.PHONY: lint
lint: my.env .docker-build
	${DC} run --rm --no-deps base /bin/bash ./docker/run_lint.sh

.PHONY: black
black: my.env .docker-build
	${DC} run --rm --no-deps base /bin/bash ./docker/run_black.sh

.PHONY: test
test: my.env .docker-build
	./docker/run_tests_in_docker.sh ${ARGS}

.PHONY: testshell
testshell: my.env .docker-build
	./docker/run_tests_in_docker.sh --shell

.PHONY: systemtest
systemtest: my.env .docker-build
	${DC} run systemtest tests/systemtest/run_tests.sh

.PHONY: systemtest-shell
systemtest-shell: my.env .docker-build
	${DC} run systemtest bash

.PHONY: test-coverage
test-coverage: my.env .docker-build
	${DC} run base py.test --cov=antenna --cov-report term-missing

.PHONY: docs
docs: my.env .docker-build
	${DC} run -u ${ANTENNA_UID} base ./bin/build_docs.sh
