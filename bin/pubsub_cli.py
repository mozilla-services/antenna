#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Pub/Sub manipulation script.
#
# Note: Run this in the base container which has access to Pub/Sub.
#
# Usage: ./bin/pubsub_cli.py [SUBCOMMAND]

import click
from google.cloud import pubsub_v1
from google.api_core.exceptions import AlreadyExists, NotFound, PermissionDenied


@click.group()
def pubsub_group():
    """Local dev environment Pub/Sub emulator manipulation script."""


@pubsub_group.command("list_crashids")
@click.argument("project_id")
@click.argument("topic_name")
@click.argument("subscription_name")
@click.pass_context
def list_crashids(ctx, project_id, topic_name, subscription_name):
    """List crashids."""
    click.echo("Listing crashids in %r for %r:" % (topic_name, subscription_name))
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
            click.echo("crash id: %s" % msg.message.data)
            ack_ids.append(msg.ack_id)

        # Acknowledges the received messages so they will not be sent again.
        subscriber.acknowledge(subscription_path, ack_ids)


@pubsub_group.command("list_topics")
@click.argument("project_id")
@click.pass_context
def list_topics(ctx, project_id):
    """List topics for this project."""
    print("Listing topics in project %s:" % project_id)
    publisher = pubsub_v1.PublisherClient()
    project_path = publisher.project_path(project_id)

    for topic in publisher.list_topics(project_path):
        click.echo(topic.name)


@pubsub_group.command("list_subscriptions")
@click.argument("project_id")
@click.argument("topic_name")
@click.pass_context
def list_subscriptions(ctx, project_id, topic_name):
    """List subscriptions for a given topic."""
    click.echo('Listing subscriptions in topic "%s":' % topic_name)
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_name)

    for subscription in publisher.list_topic_subscriptions(topic_path):
        click.echo(subscription)


@pubsub_group.command("create_topic")
@click.argument("project_id")
@click.argument("topic_name")
@click.pass_context
def create_topic(ctx, project_id, topic_name):
    """Create topic."""
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_name)

    try:
        publisher.create_topic(topic_path)
        click.echo("Topic created: %s" % topic_path)
    except AlreadyExists:
        click.echo("Topic already created.")


@pubsub_group.command("create_subscription")
@click.argument("project_id")
@click.argument("topic_name")
@click.argument("subscription_name")
@click.pass_context
def create_subscription(ctx, project_id, topic_name, subscription_name):
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_name)

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_name)
    try:
        subscriber.create_subscription(subscription_path, topic_path)
        click.echo("Subscription created: %s" % subscription_path)
    except AlreadyExists:
        click.echo("Subscription already created.")


@pubsub_group.command("delete_topic")
@click.argument("project_id")
@click.argument("topic_name")
@click.pass_context
def delete_topic(ctx, project_id, topic_name):
    """Delete a topic."""
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    topic_path = publisher.topic_path(project_id, topic_name)

    # Delete all subscriptions
    for subscription in publisher.list_topic_subscriptions(topic_path):
        click.echo("Deleting %s..." % subscription)
        subscriber.delete_subscription(subscription)

    # Delete topic
    try:
        publisher.delete_topic(topic_path)
        click.echo("Topic deleted: %s" % topic_name)
    except NotFound:
        click.echo("Topic %s does not exist." % topic_name)


if __name__ == "__main__":
    pubsub_group()
