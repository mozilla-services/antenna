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

DOCKER := $(shell which docker)
DC=${DOCKER} compose

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

.devcontainer-build:
	make devcontainerbuild

my.env:
	@if [ ! -f my.env ]; \
	then \
	echo "Copying my.env.dist to my.env..."; \
	cp docker/config/my.env.dist my.env; \
	fi

.PHONY: build
build: my.env  ## | Build docker images.
	${DC} --progress plain build ${DOCKER_BUILD_OPTS} --build-arg userid=${ANTENNA_UID} --build-arg groupid=${ANTENNA_GID} deploy-base
	${DC} --progress plain build fakesentry gcs-emulator localstack statsd
	touch .docker-build

.PHONY: setup
setup: my.env .docker-build  ## | Set up services.
	${DC} run --rm web shell ./bin/run_setup.sh

.PHONY: run
run: my.env .docker-build  ## | Run the webapp and services.
	${DC} up \
		--attach web \
		--attach fakesentry \
		web fakesentry

.PHONY: devcontainerbuild
devcontainerbuild: .env  ## | Build VS Code development container.
	${DC} build devcontainer
	touch .devcontainer-build

.PHONY: devcontainer
devcontainer: .env .devcontainer-build  ## | Run VS Code development container.
	${DC} up --detach devcontainer

.PHONY: shell
shell: my.env .docker-build  ## | Open a shell in the web image.
	${DC} run --rm web shell

.PHONY: my.env clean
clean:  ## | Remove build, test, and Python artifacts.
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
	# Run tests
	${DC} run --rm test shell ./bin/run_tests.sh

.PHONY: testshell
testshell: my.env .docker-build  ## | Open a shell in the test container.
	${DC} run --rm test shell

.PHONY: docs
docs: my.env .docker-build  ## | Generate Sphinx HTML documentation.
	${DC} run -u ${ANTENNA_UID} base shell ./bin/build_docs.sh

.PHONY: rebuildreqs
rebuildreqs: my.env .docker-build  ## | Rebuild requirements.txt file after requirements.in changes.
	${DC} run --rm --no-deps base shell pip-compile --generate-hashes --strip-extras

.PHONY: updatereqs
updatereqs: my.env .docker-build  ## | Update deps in requirements.txt file.
	${DC} run --rm --no-deps base shell pip-compile --generate-hashes --strip-extras --upgrade
