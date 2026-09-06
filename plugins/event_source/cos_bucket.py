# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""COS bucket object event source for Event-Driven Ansible.

Polls a COS bucket's object listing and yields each new (or changed) object
as an event, the polling equivalent of a bucket event notification::

    - name: react to uploaded objects
      hosts: all
      sources:
        - susunola.tencentcloud.cos_bucket:
            region: ap-guangzhou
            bucket: mybucket
            appid: "1300000000"
            prefix: images/
      rules:
        - name: process new object
          condition: event.cos.event_type == "ObjectCreated"
          action:
            run_playbook:
              name: playbooks/on_upload.yml

The first poll establishes a baseline: objects already in the bucket are
recorded but not emitted unless ``initial`` is true. Afterwards an event is
yielded for every object whose key is new or whose last-modified time has
changed since the previous poll. COS object keys are ordered lexicographically,
so the listing is walked in full each poll; ``max_objects`` caps the walk for
very large buckets (a cap can hide objects sorted after the cut-off, so it is
off by default). Polling is ``interval`` seconds apart and the listing runs in
a worker thread so the event loop stays responsive.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import argparse
import asyncio
import json
import os


def _env_or(args_key, args, env_name, default=None):
    value = args.get(args_key)
    if value:
        return value
    return os.environ.get(env_name, default)


def bucket_full_name(bucket, appid):
    """Return the ``<name>-<appid>`` form COS uses for bucket addressing.

    Accepting an already-suffixed name keeps the function idempotent when a
    full name is passed back in.
    """
    suffix = "-{0}".format(appid)
    if bucket.endswith(suffix):
        return bucket
    return "{0}{1}".format(bucket, suffix)


def list_bucket_objects(client, bucket, prefix=None, max_objects=None):
    """Walk a bucket's object listing and return the objects as plain dicts.

    Pages through ``list_objects`` (1000 objects per call, COS's hard limit)
    until the listing is exhausted or ``max_objects`` is reached. Each object
    carries ``key``, ``etag``, ``size``, ``last_modified`` and
    ``storage_class``; a truncated walk returns the first ``max_objects``
    entries in lexicographic key order.
    """
    marker = None
    objects = []
    while True:
        kwargs = {"Bucket": bucket, "MaxKeys": 1000}
        if prefix:
            kwargs["Prefix"] = prefix
        if marker:
            kwargs["Marker"] = marker
        result = client.list_objects(**kwargs) or {}
        contents = result.get("Contents") or []
        for item in contents:
            objects.append({
                "key": item.get("Key"),
                "etag": (item.get("ETag") or "").strip('"'),
                "size": item.get("Size"),
                "last_modified": item.get("LastModified"),
                "storage_class": item.get("StorageClass", "STANDARD"),
            })
            if max_objects is not None and len(objects) >= int(max_objects):
                return objects
        truncated = str(result.get("IsTruncated", "false")).lower() == "true"
        if not truncated:
            return objects
        marker = result.get("NextMarker") or (objects[-1]["key"] if objects else None)
        if marker is None:
            return objects


def _resolve_appid(args):
    """Return the account AppId used in COS bucket names.

    Prefers the ``appid`` argument, then the ``TENCENTCLOUD_APPID``
    environment variable; when neither is set the AppId is resolved via the
    STS ``GetCallerIdentity`` API (the returned ``AccountId`` is the root
    account's AppId that COS uses as the bucket name suffix).
    """
    appid = _env_or("appid", args, "TENCENTCLOUD_APPID")
    if appid:
        return str(appid)
    from tencentcloud.sts.v20180813 import models, sts_client
    from tencentcloud.common import credential as tc_credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile

    secret_id = _env_or("secret_id", args, "TENCENTCLOUD_SECRET_ID")
    secret_key = _env_or("secret_key", args, "TENCENTCLOUD_SECRET_KEY")
    token = _env_or("token", args, "TENCENTCLOUD_TOKEN")
    http_profile = HttpProfile()
    http_profile.endpoint = "sts.tencentcloudapi.com"
    http_profile.reqTimeout = 60
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client_profile.language = "en-US"
    credential = tc_credential.Credential(secret_id, secret_key, token)
    sts = sts_client.StsClient(credential, "ap-guangzhou", client_profile)
    response = sts.GetCallerIdentity(models.GetCallerIdentityRequest())
    return str(response.AccountId)


def _build_cos_client(args):
    """Construct the qcloud_cos client from args with environment fallbacks."""
    from qcloud_cos import CosConfig, CosS3Client

    secret_id = _env_or("secret_id", args, "TENCENTCLOUD_SECRET_ID")
    secret_key = _env_or("secret_key", args, "TENCENTCLOUD_SECRET_KEY")
    token = _env_or("token", args, "TENCENTCLOUD_TOKEN")
    region = _env_or("region", args, "TENCENTCLOUD_REGION")
    if not secret_id or not secret_key:
        raise RuntimeError(
            "cos_bucket requires secret_id/secret_key (or the "
            "TENCENTCLOUD_SECRET_ID/TENCENTCLOUD_SECRET_KEY environment variables)"
        )
    if not region:
        raise RuntimeError(
            "cos_bucket requires region (or TENCENTCLOUD_REGION)"
        )
    config = CosConfig(
        Region=region,
        SecretId=secret_id,
        SecretKey=secret_key,
        Token=token,
        Timeout=60,
        Endpoint=args.get("endpoint"),
    )
    return CosS3Client(config)


async def main(queue, args):
    """Poll a COS bucket and put each new/changed object on the queue.

    :param queue: asyncio.Queue consumed by ansible-rulebook.
    :param args: dict with region, bucket (and optionally appid), prefix,
        interval, initial, max_objects and endpoint.
    """
    client = _build_cos_client(args)
    region = _env_or("region", args, "TENCENTCLOUD_REGION")
    bucket = args.get("bucket")
    if not bucket:
        raise RuntimeError("cos_bucket requires bucket")
    if _env_or("appid", args, "TENCENTCLOUD_APPID"):
        bucket = bucket_full_name(bucket, _env_or("appid", args, "TENCENTCLOUD_APPID"))
    elif "-" not in bucket:
        bucket = bucket_full_name(bucket, _resolve_appid(args))

    prefix = args.get("prefix")
    interval = float(args.get("interval", 5))
    initial = bool(args.get("initial", False))
    max_objects = args.get("max_objects")
    seen = {}

    while True:
        try:
            objects = await asyncio.to_thread(
                list_bucket_objects, client, bucket, prefix, max_objects,
            )
            first_poll = not seen
            for obj in objects:
                key = obj["key"]
                stamp = obj["last_modified"]
                if seen.get(key) == stamp:
                    continue
                if first_poll and not initial:
                    seen[key] = stamp
                    continue
                seen[key] = stamp
                await queue.put({
                    "cos": dict(obj, bucket=bucket, region=region,
                                event_type="ObjectCreated"),
                })
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Keep the source alive across transient API failures; the
            # rulebook surface shows the error only if it persists.
            await queue.put({
                "cos": {"bucket": bucket, "region": region, "error": str(exc)},
            })
        await asyncio.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="COS bucket event source")
    parser.add_argument("--region", default=os.environ.get("TENCENTCLOUD_REGION"))
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--appid", default=os.environ.get("TENCENTCLOUD_APPID"))
    parser.add_argument("--prefix")
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--initial", type=bool, default=False)
    parser.add_argument("--max-objects", type=int)
    cli_args = parser.parse_args()

    async def _standalone():
        sink = asyncio.Queue()
        task = asyncio.create_task(main(sink, vars(cli_args)))
        try:
            while True:
                event = await sink.get()
                print(json.dumps(event, ensure_ascii=False, default=str))
        except KeyboardInterrupt:
            task.cancel()

    asyncio.run(_standalone())
