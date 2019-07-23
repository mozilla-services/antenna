#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Pub/Sub manipulation script.
#
# Note: Run this in the base container which has access to Pub/Sub.
#
# Usage: ./bin/pubsub_cli.py [SUBCOMMAND]

from pathlib import Path
import sys

from google.cloud import pubsub_v1
from google.api_core.exceptions import AlreadyExists, NotFound, PermissionDenied

# Add parent to sys.path before importing antenna
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from antenna.app import build_config_manager  # noqa


HELP_TEXT = """\
Usage: ./bin/pubsub_cli.py [SUBCOMMAND]

Local dev environment Pub/Sub emulator manipulation script.
"""


def list_crashids(project_id, topic_name, subscription_name):
    """List crashids."""
    print("Listing crashids in %r for %r:" % (topic_name, subscription_name))
    subscriber = pubsub_v1.SubscriberClient()
    topic_path = subscriber.topic_path(project_id, topic_name)
    subscription_path = subscriber.subscription_path(project_id, subscription_name)

    # Create subscription for listing items in the topic
    try:
        subscriber.create_subscription(subscription_path, topic_path)
    except (AlreadyExists, PermissionDenied):
        subscriber.get_subscription(subscription_path)

    while True:
        response = subscriber.pull(
            subscription_path, max_messages=1, return_immediately=True
        )
        if not response.received_messages:
            break

        ack_ids = []
        for msg in response.received_messages:
            print("crash id: %s" % msg.message.data)
            ack_ids.append(msg.ack_id)

        # Acknowledges the received messages so they will not be sent again.
        subscriber.acknowledge(subscription_path, ack_ids)


def list_topics(project_id, topic_name, subscription_name):
    """List topics for this project."""
    print("Listing topics in project %s:" % project_id)
    publisher = pubsub_v1.PublisherClient()
    project_path = publisher.project_path(project_id)

    for topic in publisher.list_topics(project_path):
        print(topic.name)


def list_subscriptions(project_id, topic_name, subscription_name):
    """List subscriptions for a given topic."""
    print('Listing subscriptions in topic "%s":' % topic_name)
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_name)

    for subscription in publisher.list_topic_subscriptions(topic_path):
        print(subscription)


def create_topic(project_id, topic_name, subscription_name):
    """Create topic and subscription."""
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_name)

    try:
        publisher.create_topic(topic_path)
        print("Topic created: %s" % topic_path)
    except AlreadyExists:
        print("Topic already created.")

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_name)
    try:
        subscriber.create_subscription(subscription_path, topic_path)
        print("Subscription created: %s" % subscription_path)
    except AlreadyExists:
        print("Subscription already created.")
        pass


def delete_topic(project_id, topic_name, subscription_name):
    """Delete a topic."""
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    topic_path = publisher.topic_path(project_id, topic_name)

    # Delete all subscriptions
    for subscription in publisher.list_topic_subscriptions(topic_path):
        print("Deleting %s..." % subscription)
        subscriber.delete_subscription(subscription)

    # Delete topic
    try:
        publisher.delete_topic(topic_path)
        print("Topic deleted: %s" % topic_name)
    except NotFound:
        pass


def print_help():
    """Print help text."""
    print(HELP_TEXT)
    for cmd, fun in SUBCOMMANDS.items():
        print("%s: %s" % (cmd, fun.__doc__.splitlines()[0].strip()))
    return 0


SUBCOMMANDS = {
    "create_topic": create_topic,
    "delete_topic": delete_topic,
    "list_subscriptions": list_subscriptions,
    "list_crashids": list_crashids,
    "list_topics": list_topics,
    "help": print_help,
}


def main():
    args = sys.argv[1:]
    if not args:
        print_help()
        return 1

    config = build_config_manager()

    if not config("PUBSUB_EMULATOR_HOST", default=""):
        print("WARNING: You are running against the real GCP and not the emulator.")

    project_id = config("CRASHPUBLISH_PROJECT_ID")
    topic_name = config("CRASHPUBLISH_TOPIC_NAME")
    subscription_name = config("CRASHPUBLISH_SUBSCRIPTION_NAME")

    if args[0] in SUBCOMMANDS:
        return SUBCOMMANDS[args[0]](project_id, topic_name, subscription_name)

    print("Subcommand %s does not exist." % args[0])
    return 1


if __name__ == "__main__":
    sys.exit(main())
