#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Pub/Sub manipulation script.
#
# Note: Run this in the base container which has access to Pub/Sub.
#
# Usage: ./bin/pubsub_cli.py [SUBCOMMAND]

import click
from google.cloud import pubsub_v1
from google.api_core.exceptions import AlreadyExists, NotFound


@click.group()
def pubsub_group():
    """Local dev environment Pub/Sub emulator manipulation script."""


@pubsub_group.command("list_topics")
@click.argument("project_id")
@click.pass_context
def list_topics(ctx, project_id):
    """List topics for this project."""
    raise NotImplementedError(
        "pubsub emulator times out for list_topics as of gcloud cli 463.0.0"
    )

    print("Listing topics in project %s:" % project_id)
    publisher = pubsub_v1.PublisherClient()

    for topic in publisher.list_topics(project=project_id):
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

    for subscription in publisher.list_topic_subscriptions(topic=topic_path):
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
        publisher.create_topic(name=topic_path)
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
        subscriber.create_subscription(name=subscription_path, topic=topic_path)
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
    for subscription in publisher.list_topic_subscriptions(topic=topic_path):
        click.echo("Deleting %s..." % subscription)
        subscriber.delete_subscription(subscription=subscription)

    # Delete topic
    try:
        publisher.delete_topic(topic=topic_path)
        click.echo("Topic deleted: %s" % topic_name)
    except NotFound:
        click.echo("Topic %s does not exist." % topic_name)


@pubsub_group.command("publish")
@click.argument("project_id")
@click.argument("topic_name")
@click.argument("crash_id")
@click.pass_context
def publish(ctx, project_id, topic_name, crash_id):
    """Publish crash_id to a given topic."""
    click.echo('Publishing crash_id to topic "%s":' % topic_name)
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_name)

    future = publisher.publish(topic_path, crash_id.encode("utf-8"), timeout=5)
    click.echo(future.result())


@pubsub_group.command("pull")
@click.argument("project_id")
@click.argument("subscription_name")
@click.option("--ack/--no-ack", is_flag=True, default=False)
@click.option("--max-messages", default=1, type=int)
@click.pass_context
def pull(ctx, project_id, subscription_name, ack, max_messages):
    """Pull crash id from a given subscription."""
    click.echo('Pulling crash id from subscription "%s":' % subscription_name)
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_name)

    response = subscriber.pull(
        subscription=subscription_path, max_messages=max_messages
    )
    if not response.received_messages:
        return

    ack_ids = []
    for msg in response.received_messages:
        click.echo("crash id: %s" % msg.message.data)
        ack_ids.append(msg.ack_id)

    if ack:
        # Acknowledges the received messages so they will not be sent again.
        subscriber.acknowledge(subscription=subscription_path, ack_ids=ack_ids)


if __name__ == "__main__":
    pubsub_group()
