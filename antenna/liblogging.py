# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Utilities for logging configuration and usage.
"""

import logging
import logging.config
import socket

from everett.manager import (
    get_config_for_class,
    get_runtime_config,
    generate_uppercase_key,
)


_IS_LOGGING_SET_UP = False

LOGGER = logging.getLogger(__name__)


def set_up_logging(logging_level, debug=False, host_id=None, processname=None):
    """Initialize Python logging configuration.

    Note: This only sets up logging once per process. Additional calls will get ignored.

    :arg logging_level: the level to log at
    :arg debug: whether or not to log to the console in an easier-to-read fashion
    :arg host_id: the host id to log
    :arg processname: the process name to log

    """
    global _IS_LOGGING_SET_UP
    if _IS_LOGGING_SET_UP:
        return

    host_id = host_id or socket.gethostname()
    processname = processname or "main"

    class AddHostID(logging.Filter):
        def filter(self, record):
            record.host_id = host_id
            return True

    class AddProcessName(logging.Filter):
        def filter(self, record):
            record.processname = processname
            return True

    dc = {
        "version": 1,
        "disable_existing_loggers": True,
        "filters": {
            "add_hostid": {"()": AddHostID},
            "add_processname": {"()": AddProcessName},
        },
        "formatters": {
            "app": {
                "format": "%(asctime)s %(levelname)s - %(processname)s - %(name)s - %(message)s"
            },
            "mozlog": {
                "()": "dockerflow.logging.JsonLogFormatter",
                "logger_name": "antenna",
            },
        },
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "app",
                "filters": ["add_hostid", "add_processname"],
            },
            "mozlog": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "mozlog",
                "filters": ["add_hostid", "add_processname"],
            },
        },
        "loggers": {
            "antenna": {"level": logging_level},
            "falcon": {"level": logging_level},
            "fillmore": {"level": logging.ERROR},
            "markus": {"level": logging.ERROR},
        },
        "root": {"handlers": ["mozlog"], "level": "WARNING"},
    }

    if debug:
        # In debug mode (only the local development environment), we log to the console
        # in a human-readable fashion and add a markus logger
        dc["loggers"]["markus"] = {"level": logging.INFO}
        dc["root"]["handlers"] = ["console"]

    logging.config.dictConfig(dc)
    LOGGER.info(
        f"set up logging logging_level={logging_level} debug={debug} "
        + f"host_id={host_id} processname={processname}"
    )
    _IS_LOGGING_SET_UP = True


def traverse_tree(instance, namespace=None):
    """Traverses tree of components using "get_components" for branches.

    :arg instance: the instance to traverse
    :arg namespace: the list of strings forming the namespace or None

    :returns: list of ``(namespace, key, value, option, component)``

    """
    namespace = namespace or []

    this_options = get_config_for_class(instance.__class__)
    if not this_options:
        return []

    options = [
        (namespace, key, option, instance)
        for key, (option, cls) in this_options.items()
    ]

    if hasattr(instance, "get_components"):
        for component_ns, component in instance.get_components().items():
            options.extend(traverse_tree(component, namespace + [component_ns]))

    return options


def log_config(logger, config, component):
    """Log configuration for a given component.

    :arg logger: a Python logging logger
    :arg config: the config manager
    :arg component: the component with a Config property to log the configuration of

    """
    runtime_config = get_runtime_config(
        config=config, component=component, traverse=traverse_tree
    )
    for ns, key, value, _ in runtime_config:
        # This gets rid of NO_VALUE
        value = value or ""

        # "secret" is an indicator that the value is secret and shouldn't get logged
        if "secret" in key.lower() and value:
            value = "*****"

        full_key = generate_uppercase_key(key, ns).upper()
        logger.info(f"{full_key}={value}")
