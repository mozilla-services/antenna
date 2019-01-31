ANTENNA_ENV ?= "dev.env"
DC := $(shell which docker-compose)
HOSTUSER := $(shell id -u):$(shell id -g)

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
	@echo "test             - run unit tests"
	@echo "systemtest       - run system tests against a running Antenna instance"
	@echo "systemtest-shell - open a shell in the systemtest container"
	@echo "test-coverage    - run tests and generate coverage report in cover/"
	@echo "docs             - generate Sphinx HTML documentation, including API docs"
	@echo ""
	@echo "Set ANTENNA_ENV=/path/to/env/file for configuration."

# Dev configuration steps
.docker-build:
	make build

.PHONY: build
build:
	ANTENNA_ENV=empty.env ${DC} build deploy-base
	touch .docker-build

.PHONY: run
run: .docker-build
	ANTENNA_ENV=${ANTENNA_ENV} ${DC} up web

.PHONY: shell
shell: .docker-build
	ANTENNA_ENV=empty.env ${DC} run base bash

.PHONY: clean
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
lint: .docker-build
	ANTENNA_ENV=empty.env ${DC} run base flake8 --statistics antenna tests/unittest/
	ANTENNA_ENV=empty.env ${DC} run base bandit -r antenna/

.PHONY: test
test: .docker-build
	ANTENNA_ENV=empty.env ${DC} run base py.test

.PHONY: systemtest
systemtest: .docker-build
	ANTENNA_ENV=dev.env ${DC} run systemtest tests/systemtest/run_tests.sh

.PHONY: systemtest-shell
systemtest-shell: .docker-build
	ANTENNA_ENV=dev.env ${DC} run systemtest bash

.PHONY: test-coverage
test-coverage: .docker-build
	ANTENNA_ENV=empty.env ${DC} run base py.test --cov=antenna --cov-report term-missing

.PHONY: docs
docs: .docker-build
	ANTENNA_ENV=empty.env ${DC} run -u ${HOSTUSER} base ./bin/build_docs.sh
