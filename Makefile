ANTENNA_ENV ?= "prod.env"
DC := $(shell which docker-compose)

default:
	@echo "You need to specify a subcommand."
	@exit 1

help:
	@echo "build         - build docker containers for dev"
	@echo "run           - docker-compose up the entire system for dev"
	@echo ""
	@echo "shell         - open a shell in the base container"
	@echo "clean         - remove all build, test, coverage and Python artifacts"
	@echo "lint          - check style with flake8"
	@echo "test          - run unit tests"
	@echo "test-system   - run system tests against a running Antenna instance"
	@echo "test-coverage - run tests and generate coverage report in cover/"
	@echo "docs          - generate Sphinx HTML documentation, including API docs"

# Dev configuration steps
.docker-build:
	make build

build:
	ANTENNA_ENV=empty.env ${DC} build deploy-base
	ANTENNA_ENV=empty.env ${DC} build dev-base
	ANTENNA_ENV=empty.env ${DC} build base
	touch .docker-build

run: .docker-build
	ANTENNA_ENV=${ANTENNA_ENV} ${DC} up web

shell: .docker-build
	ANTENNA_ENV=empty.env ${DC} run base bash

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
	ANTENNA_ENV=empty.env ${DC} run base rm -rf cover

	# docs files
	-rm -rf docs/_build/

	# state files
	-rm .docker-build
	-rm -rf fakes3_root/

lint: .docker-build
	ANTENNA_ENV=empty.env ${DC} run base flake8 --statistics antenna tests/unittest/

test: .docker-build
	ANTENNA_ENV=empty.env ${DC} run base py.test

test-system: .docker-build
	ANTENNA_ENV=${ANTENNA_ENV} ${DC} run systemtest py.test -v tests/systemtest/

test-system-shell: .docker-build
	ANTENNA_ENV=${ANTENNA_ENV} ${DC} run systemtest bash

test-coverage: .docker-build
	ANTENNA_ENV=empty.env ${DC} run base py.test --with-coverage --cover-package=antenna --cover-inclusive --cover-html

docs: .docker-build
	ANTENNA_ENV=empty.env ${DC} run base ./bin/build_docs.sh

.PHONY: default clean build docs lint run shell test test-system test-system-shell test-coverage
