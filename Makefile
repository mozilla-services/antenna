# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

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

.DEFAULT_GOAL := help
.PHONY: help
help:
	@echo "Usage: make RULE"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' Makefile \
		| grep -v grep \
	    | sed -n 's/^\(.*\): \(.*\)##\(.*\)/\1\3/p' \
	    | column -t  -s '|'
	@echo ""
	@echo "Adjust your my.env file to set configuration."
	@echo ""
	@echo "See https://antenna.readthedocs.io/ for more documentation."

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
build: my.env  ## | Build docker images.
	${DC} build ${DOCKER_BUILD_OPTS} --build-arg userid=${ANTENNA_UID} --build-arg groupid=${ANTENNA_GID} deploy-base
	touch .docker-build

.PHONY: setup
setup: my.env .docker-build  ## | Set up services.
	${DC} run --rm web shell ./bin/run_setup.sh

.PHONY: run
run: my.env .docker-build  ## | Run the webapp and services.
	${DC} up web

.PHONY: shell
shell: my.env .docker-build  ## | Open a shell in the web image.
	${DC} run --rm web shell

.PHONY: my.env clean
clean:  ## | Remove build, test, coverage, and Python artifacts.
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
lint: my.env .docker-build  ## | Lint code.
	${DC} run --rm --no-deps base shell ./bin/run_lint.sh

.PHONY: lintfix
lintfix: my.env .docker-build  ## | Reformat code.
	${DC} run --rm --no-deps base shell ./bin/run_lint.sh --fix

.PHONY: test
test: my.env .docker-build  ## | Run unit tests.
	# Make sure services are started up
	${DC} up -d localstack-s3
	${DC} up -d localstack-sqs
	${DC} up -d statsd
	# Run tests
	${DC} run --rm test shell ./bin/run_tests.sh

.PHONY: test-ci
test-ci: my.env .docker-build  ## | Run unit tests in CI.
	# Make sure services are started up
	${DC} up -d localstack-s3
	${DC} up -d localstack-sqs
	${DC} up -d statsd
	# Run tests in test-ci container
	${DC} run --rm test-ci shell ./bin/run_tests.sh

.PHONY: testshell
testshell: my.env .docker-build  ## | Open a shell in the test container.
	${DC} run --rm test shell

.PHONY: test-coverage
test-coverage: my.env .docker-build  ## | Run test coverage report.
	${DC} run --rm test shell ./bin/run_tests.sh --cov=antenna --cov-report term-missing

.PHONY: docs
docs: my.env .docker-build  ## | Generate Sphinx HTML documentation.
	${DC} run -u ${ANTENNA_UID} base shell ./bin/build_docs.sh
