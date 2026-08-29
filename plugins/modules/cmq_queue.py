#!/usr/bin/python
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: cmq_queue
short_description: Manage Tencent Cloud CMQ queues
version_added: "0.14.0"
description: Manages CMQ queue lifecycle and delivery settings using the CMQ management actions.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  queue_name: {description: Queue name., type: str, required: true}
  max_msg_heap_num: {description: Maximum queued message count., type: int, default: 10000000}
  polling_wait_seconds: {description: Long-poll wait time in seconds., type: int, default: 0}
  visibility_timeout: {description: Message visibility timeout in seconds., type: int, default: 30}
  max_msg_size: {description: Maximum message size in bytes., type: int, default: 65536}
  msg_retention_seconds: {description: Message retention period in seconds., type: int, default: 345600}
  rewind_seconds: {description: Maximum message rewind period in seconds., type: int, default: 0}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r"""
- susunola.tencentcloud.cmq_queue:
    queue_name: jobs
    polling_wait_seconds: 10
    visibility_timeout: 60
"""
RETURN = r"""queue: {description: Queue metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_cmq():
    from tencentcloud.cmq.v20190304 import cmq_client, models

    return models, cmq_client


def build_describe_request(models, name):
    r = models.DescribeQueueDetailRequest()
    r.QueueName = name
    r.Offset = 0
    r.Limit = 1
    return r


def build_create_payload(p):
    return {
        "QueueName": p["queue_name"],
        "MaxMsgHeapNum": p["max_msg_heap_num"],
        "PollingWaitSeconds": p["polling_wait_seconds"],
        "VisibilityTimeout": p["visibility_timeout"],
        "MaxMsgSize": p["max_msg_size"],
        "MsgRetentionSeconds": p["msg_retention_seconds"],
        "RewindSeconds": p["rewind_seconds"],
    }


def build_update_payload(p):
    return build_create_payload(p)


def build_delete_payload(name):
    return {"QueueName": name}


def _desired(p):
    return build_create_payload(p)


def _find(response):
    items = response.QueueSet or []
    return items[0]._serialize(allow_none=True) if items else None


def _raw(module, client, action, payload):
    return module.sdk_call(lambda request: client.call(action, request), payload)


def run_module():
    spec = {
        "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
        "queue_name": {"type": "str", "required": True},
        "max_msg_heap_num": {"type": "int", "default": 10000000},
        "polling_wait_seconds": {"type": "int", "default": 0},
        "visibility_timeout": {"type": "int", "default": 30},
        "max_msg_size": {"type": "int", "default": 65536},
        "msg_retention_seconds": {"type": "int", "default": 345600},
        "rewind_seconds": {"type": "int", "default": 0},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load_cmq()
    client = module.create_client(cm.CmqClient, "cmq.tencentcloudapi.com")
    try:
        current = _find(module.sdk_call(client.DescribeQueueDetail, build_describe_request(models, p["queue_name"])))
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, queue=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                _raw(module, client, "DeleteQueue", build_delete_payload(p["queue_name"]))
            module.exit_json(changed=True, **(diff or {}), queue=current if module.check_mode else None)
        desired = _desired(p)
        comparable = {k: current.get(k) for k in desired} if current else None
        if comparable == desired:
            module.exit_json(changed=False, queue=current)
        diff = maybe_diff(module, comparable, desired)
        if not module.check_mode:
            _raw(module, client, "ModifyQueueAttribute" if current else "CreateQueue", build_update_payload(p) if current else build_create_payload(p))
        module.exit_json(changed=True, **(diff or {}), queue=current if module.check_mode else desired)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
