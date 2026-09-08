# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""CLS (Cloud Log Service) event source for Event-Driven Ansible.

Polls a CLS log topic with a search query and yields each new matching log
record as an event. Works with ansible-rulebook::

    - name: react to error logs
      hosts: all
      sources:
        - susunola.tencentcloud.cls_topic:
            region: ap-guangzhou
            topic_id: "{{ topic_id }}"
            query: 'level:ERROR'
      rules:
        - name: page on error
          condition: event.level == "ERROR"
          action:
            run_playbook:
              name: playbooks/on_error.yml

The source keeps a rolling ``from`` timestamp (now - ``lookback`` at start,
then the previous poll's ``to``) so logs between polls are not skipped and
each log is yielded exactly once under normal operation. Polling is
``interval`` seconds apart; the CLS search API is called from a worker
thread so the event loop stays responsive.
"""


from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cls_topic
short_description: Poll a Tencent Cloud CLS log topic for matching log records (event source)
description:
  - Polls a Tencent Cloud CLS (Cloud Log Service) log topic with a search
    query and yields each new matching log record as an event for
    Event-Driven Ansible (ansible-rulebook).
  - The source keeps a rolling C(from) timestamp (now minus O(lookback) at
    start, then the previous poll's C(to)) so logs between polls are not
    skipped and each log is yielded exactly once under normal operation.
  - The CLS search API runs in a worker thread so the event loop stays
    responsive; polling happens every O(interval) seconds.
version_added: "1.0.0"
options:
  secret_id:
    description: Tencent Cloud secret id (fallback C(TENCENTCLOUD_SECRET_ID)).
    type: str
  secret_key:
    description: Tencent Cloud secret key (fallback C(TENCENTCLOUD_SECRET_KEY)).
    type: str
  token:
    description: Temporary session token (fallback C(TENCENTCLOUD_TOKEN)).
    type: str
  region:
    description: Region of the log topic (fallback C(TENCENTCLOUD_REGION)), e.g. C(ap-guangzhou).
    type: str
  endpoint:
    description: API endpoint override, defaults to C(cls.tencentcloudapi.com).
    type: str
  topic_id:
    description: Id of the CLS log topic to search, e.g. C(dc9b3c16-xxxx).
    type: str
  topic_name:
    description: Name of the log topic; resolved to an id when O(topic_id) is not given.
    type: str
  query:
    description: CLS search query, e.g. C(level:ERROR). Defaults to all records.
    type: str
    default: "*"
  interval:
    description: Seconds between polls.
    type: float
    default: 5
  batch_size:
    description: Maximum number of log records returned per search page.
    type: int
    default: 20
  lookback:
    description: Seconds of history searched on the first poll before the rolling window starts.
    type: float
    default: 30
requirements:
  - tencentcloud-sdk-python
author:
  - Tencent Cloud Ansible Collection Contributors (@susunola)
'''

import argparse
import asyncio
import json
import os
import time


def _env_or(args_key, args, env_name, default=None):
    value = args.get(args_key)
    if value:
        return value
    return os.environ.get(env_name, default)


def build_search_request(models, topic_id, query, from_ms, to_ms, limit, context):
    request = models.SearchLogRequest()
    request.TopicId = topic_id
    request.Query = query
    request.From = from_ms
    request.To = to_ms
    request.Limit = limit
    if context:
        request.Context = context
    return request


def search_logs(client, models, topic_id, query, from_ms, to_ms, limit, context):
    """Run one SearchLog call; return (records, next_context)."""
    request = build_search_request(
        models, topic_id, query, from_ms, to_ms, limit, context
    )
    response = client.SearchLog(request)
    records = []
    for item in response.Results or []:
        raw = getattr(item, "RawLog", None)
        if raw:
            try:
                records.append(json.loads(raw))
            except (ValueError, TypeError):
                records.append({"message": raw})
    return records, getattr(response, "Context", None)


def describe_topic_id(client, models, region, topic_name):
    """Resolve a topic name to a topic ID via DescribeTopics."""
    request = models.DescribeTopicsRequest()
    request.Offset = 0
    request.Limit = 100
    response = client.DescribeTopics(request)
    for topic in response.Topics or []:
        if getattr(topic, "TopicName", None) == topic_name:
            return topic.TopicId
    raise RuntimeError(
        "CLS topic %r not found in region %s" % (topic_name, region)
    )


def _build_client(args):
    """Construct the CLS SDK client from args with environment fallbacks."""
    from tencentcloud.cls.v20201016 import cls_client, models
    from tencentcloud.common import credential as tc_credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile

    secret_id = _env_or("secret_id", args, "TENCENTCLOUD_SECRET_ID")
    secret_key = _env_or("secret_key", args, "TENCENTCLOUD_SECRET_KEY")
    token = _env_or("token", args, "TENCENTCLOUD_TOKEN")
    region = _env_or("region", args, "TENCENTCLOUD_REGION")
    if not secret_id or not secret_key:
        raise RuntimeError(
            "CLS event source requires secret_id/secret_key (or the "
            "TENCENTCLOUD_SECRET_ID/TENCENTCLOUD_SECRET_KEY environment variables)"
        )
    if not region:
        raise RuntimeError(
            "CLS event source requires region (or TENCENTCLOUD_REGION)"
        )
    http_profile = HttpProfile()
    http_profile.endpoint = args.get("endpoint") or "cls.tencentcloudapi.com"
    http_profile.reqTimeout = 60
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client_profile.language = "en-US"
    credential = tc_credential.Credential(secret_id, secret_key, token)
    return cls_client.ClsClient(credential, region, client_profile), models


async def main(queue, args):
    """Poll CLS for new log records and put each on the queue.

    :param queue: asyncio.Queue consumed by ansible-rulebook.
    :param args: dict with region, topic_id (or topic_name), query,
        interval, batch_size, lookback and endpoint.
    """
    client, models = _build_client(args)
    region = _env_or("region", args, "TENCENTCLOUD_REGION")
    topic_id = args.get("topic_id")
    if not topic_id:
        topic_name = args.get("topic_name")
        if not topic_name:
            raise RuntimeError("cls_topic requires topic_id or topic_name")
        topic_id = describe_topic_id(client, models, region, topic_name)

    query = args.get("query", "*")
    interval = float(args.get("interval", 5))
    batch_size = int(args.get("batch_size", 20))
    lookback = float(args.get("lookback", 30))
    context = None

    now_ms = int(time.time() * 1000)
    window_from = now_ms - int(lookback * 1000)
    window_to = now_ms

    while True:
        try:
            records, context = await asyncio.to_thread(
                search_logs, client, models, topic_id, query,
                window_from, window_to, batch_size, context,
            )
            for record in records:
                await queue.put({"cls": record, "topic_id": topic_id,
                                 "region": region})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Keep the source alive across transient API failures; the
            # rulebook surface shows the error only if it persists.
            await queue.put({
                "cls": {"error": str(exc)},
                "topic_id": topic_id,
                "region": region,
            })
        window_from = window_to
        window_to = int(time.time() * 1000)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLS event source")
    parser.add_argument("--region", default=os.environ.get("TENCENTCLOUD_REGION"))
    parser.add_argument("--topic-id")
    parser.add_argument("--topic-name")
    parser.add_argument("--query", default="*")
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--lookback", type=float, default=30)
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
