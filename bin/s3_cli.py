#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Manipulates S3 in local dev environment.
#
# Run this in the Docker container.

import os
import pathlib

import boto3
from botocore.client import ClientError, Config
import click


def get_client():
    session = boto3.session.Session(
        aws_access_key_id=os.environ.get("CRASHMOVER_CRASHSTORAGE_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get(
            "CRASHMOVER_CRASHSTORAGE_SECRET_ACCESS_KEY"
        ),
    )
    client = session.client(
        service_name="s3",
        config=Config(s3={"addressing_style": "path"}),
        endpoint_url=os.environ.get("CRASHMOVER_CRASHSTORAGE_ENDPOINT_URL"),
    )
    return client


@click.group()
def s3_group():
    """Manipulate S3 in local dev environment."""


@s3_group.command("create")
@click.argument("bucket")
@click.pass_context
def create_bucket(ctx, bucket):
    """Create a new S3 bucket."""
    conn = get_client()
    try:
        conn.head_bucket(Bucket=bucket)
        click.echo("Bucket %s exists." % bucket)
    except ClientError:
        conn.create_bucket(Bucket=bucket)
        click.echo("Bucket %s created." % bucket)


@s3_group.command("delete")
@click.argument("bucket")
@click.pass_context
def delete_bucket(ctx, bucket):
    """Delete an S3 bucket."""
    conn = get_client()
    try:
        conn.head_bucket(Bucket=bucket)
    except ClientError:
        click.echo("Bucket %s does not exist." % bucket)
        return

    # Delete any objects in the bucket
    resp = conn.list_objects(Bucket=bucket)
    for obj in resp.get("Contents", []):
        key = obj["Key"]
        conn.delete_object(Bucket=bucket, Key=key)

    # Then delete the bucket
    conn.delete_bucket(Bucket=bucket)


@s3_group.command("list_buckets")
@click.pass_context
def list_buckets(ctx):
    """List S3 buckets."""
    conn = get_client()
    resp = conn.list_buckets()
    for bucket in resp["Buckets"]:
        click.echo("%s\t%s" % (bucket["Name"], bucket["CreationDate"]))


@s3_group.command("list_objects")
@click.option("-d", "--details", default=False, type=bool, help="With details")
@click.argument("bucket")
@click.pass_context
def list_objects(ctx, bucket, details):
    """List the contents of a bucket."""
    conn = get_client()
    try:
        conn.head_bucket(Bucket=bucket)
    except ClientError:
        click.echo("Bucket %s does not exist." % bucket)
        return

    resp = conn.list_objects_v2(Bucket=bucket)
    for item in resp.get("Contents", []):
        if details:
            click.echo(f"{item['Key']}\t{item['Size']}\t{item['LastModified']}")
        else:
            click.echo(f"{item['Key']}")


@s3_group.command("download")
@click.argument("bucket")
@click.argument("key")
@click.argument("outputdir")
@click.pass_context
def download_file(ctx, bucket, key, outputdir):
    conn = get_client()
    try:
        conn.head_bucket(Bucket=bucket)
    except ClientError:
        click.echo(f"Bucket {bucket} does not exist.")
        return

    keypath = pathlib.Path(outputdir) / pathlib.Path(key)
    if not keypath.parent.exists():
        keypath.parent.mkdir(parents=True)

    if not keypath.parent.is_dir():
        click.echo(f"{keypath.parent} exists but is not a directory")

    with keypath.open("wb") as fp:
        conn.download_fileobj(bucket, key, fp)


if __name__ == "__main__":
    s3_group()
