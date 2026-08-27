# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""CMQ (Cloud Message Queue) event source for Event-Driven Ansible.

Long-polls a CMQ queue and yields each received message as an event::

    - name: react to CMQ messages
      hosts: all
      sources:
        - susunola.tencentcloud.cmq_queue:
            region: ap-guangzhou
            queue_name: order-events
      rules:
        - name: process order
          condition: event.cmq.MsgBody is defined
          action:
            run_playbook:
              name: playbooks/process_order.yml

The SDK ReceiveMessage call blocks for up to ``polling_wait_seconds``
(0-30); it runs in a worker thread so the event loop stays responsive.
When ``acknowledge`` is true (default) each message is deleted after it is
yielded, so the queue drains as events are processed; set it to false to
keep the messages in the queue (they become visible again after the
visibility timeout).
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


def receive_message(client, models, queue_name, polling_wait_seconds):
    request = models.ReceiveMessageRequest()
    request.QueueName = queue_name
    request.PollingWaitSeconds = polling_wait_seconds
    return client.ReceiveMessage(request)


def delete_message(client, models, queue_name, receipt_handle):
    request = models.DeleteMessageRequest()
    request.QueueName = queue_name
    request.ReceiptHandle = receipt_handle
    return client.DeleteMessage(request)


def _build_client(args):
    """Construct the CMQ SDK client from args with environment fallbacks."""
    from tencentcloud.cmq.v20190304 import cmq_client, models
    from tencentcloud.common import credential as tc_credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile

    secret_id = _env_or("secret_id", args, "TENCENTCLOUD_SECRET_ID")
    secret_key = _env_or("secret_key", args, "TENCENTCLOUD_SECRET_KEY")
    token = _env_or("token", args, "TENCENTCLOUD_TOKEN")
    region = _env_or("region", args, "TENCENTCLOUD_REGION")
    if not secret_id or not secret_key:
        raise RuntimeError(
            "CMQ event source requires secret_id/secret_key (or the "
            "TENCENTCLOUD_SECRET_ID/TENCENTCLOUD_SECRET_KEY environment variables)"
        )
    if not region:
        raise RuntimeError(
            "CMQ event source requires region (or TENCENTCLOUD_REGION)"
        )
    http_profile = HttpProfile()
    http_profile.endpoint = args.get("endpoint") or "cmq.tencentcloudapi.com"
    http_profile.reqTimeout = 60
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client_profile.language = "en-US"
    credential = tc_credential.Credential(secret_id, secret_key, token)
    return cmq_client.CmqClient(credential, region, client_profile), models


async def main(queue, args):
    """Long-poll a CMQ queue and put each message on the queue.

    :param queue: asyncio.Queue consumed by ansible-rulebook.
    :param args: dict with region, queue_name, polling_wait_seconds,
        acknowledge, idle_interval and endpoint.
    """
    client, models = _build_client(args)
    region = _env_or("region", args, "TENCENTCLOUD_REGION")
    queue_name = args.get("queue_name")
    if not queue_name:
        raise RuntimeError("cmq_queue requires queue_name")
    polling_wait = int(args.get("polling_wait_seconds", 20))
    acknowledge = bool(args.get("acknowledge", True))
    idle_interval = float(args.get("idle_interval", 1))

    while True:
        try:
            response = await asyncio.to_thread(
                receive_message, client, models, queue_name, polling_wait
            )
            msg_body = getattr(response, "MsgBody", None)
            if msg_body is None:
                await asyncio.sleep(idle_interval)
                continue
            receipt = getattr(response, "ReceiptHandle", None)
            event = {
                "cmq": {
                    "queue_name": queue_name,
                    "msg_id": getattr(response, "MsgId", None),
                    "msg_body": msg_body,
                    "dequeue_count": getattr(response, "DequeueCount", None),
                    "enqueue_time": getattr(response, "EnqueueTime", None),
                    "first_dequeue_time": getattr(response, "FirstDequeueTime", None),
                    "region": region,
                }
            }
            try:
                event["cmq"]["msg_body_json"] = json.loads(msg_body)
            except (ValueError, TypeError):
                pass
            await queue.put(event)
            if acknowledge and receipt:
                await asyncio.to_thread(
                    delete_message, client, models, queue_name, receipt
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await queue.put({
                "cmq": {"queue_name": queue_name, "error": str(exc),
                        "region": region},
            })
            await asyncio.sleep(idle_interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CMQ event source")
    parser.add_argument("--region", default=os.environ.get("TENCENTCLOUD_REGION"))
    parser.add_argument("--queue-name", required=True)
    parser.add_argument("--polling-wait-seconds", type=int, default=20)
    parser.add_argument("--acknowledge", type=bool, default=True)
    parser.add_argument("--idle-interval", type=float, default=1)
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
