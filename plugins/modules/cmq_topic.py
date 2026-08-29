#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: cmq_topic
short_description: Manage Tencent Cloud CMQ topics
version_added: "0.14.0"
description: Creates, updates and deletes CMQ topics idempotently.
options:
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  topic_name: {type: str, required: true, description: Topic name.}
  max_msg_size: {type: int, default: 65536, description: Maximum message size.}
  message_retention_seconds: {type: int, default: 86400, description: Message retention period.}
  filter_type: {type: int, choices: [1, 2], default: 1, description: Subscription filter type.}
  trace: {type: bool, default: false, description: Enable message tracing.}
  tags: {type: dict, default: {}, description: Tags applied at creation.}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cmq_topic:
    topic_name: order-events
    message_retention_seconds: 172800
"""
RETURN = r"""topic: {description: Topic metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client

    return models, tdmq_client


def describe_request(models, name):
    request = models.DescribeCmqTopicsRequest()
    request.Offset, request.Limit, request.TopicName = 0, 100, name
    return request


def tags(models, values):
    result = []
    for key, value in sorted(values.items()):
        item = models.Tag()
        item.Key, item.Value = str(key), str(value)
        result.append(item)
    return result


def desired(p):
    return {
        "TopicName": p["topic_name"],
        "MaxMsgSize": p["max_msg_size"],
        "MsgRetentionSeconds": p["message_retention_seconds"],
        "FilterType": p["filter_type"],
        "Trace": p["trace"],
    }


def find(module, client, models, name):
    response = module.sdk_call(client.DescribeCmqTopics, describe_request(models, name))
    items = getattr(response, "TopicList", None) or []
    matches = [x._serialize(allow_none=True) for x in items if x.TopicName == name]
    if len(matches) > 1:
        module.fail_json(msg="Multiple CMQ topics have the requested name", topic_name=name)
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "topic_name": {"required": True},
            "max_msg_size": {"type": "int", "default": 65536},
            "message_retention_seconds": {"type": "int", "default": 86400},
            "filter_type": {"type": "int", "choices": [1, 2], "default": 1},
            "trace": {"type": "bool", "default": False},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["topic_name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, topic=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteCmqTopicRequest()
                request.TopicName = p["topic_name"]
                module.sdk_call(client.DeleteCmqTopic, request)
            module.exit_json(changed=True, **(diff or {}), topic=current if module.check_mode else None)
        target = desired(p)
        before = {key: current.get(key) for key in target} if current else None
        if before == target:
            module.exit_json(changed=False, topic=current)
        if current:
            require_immutable_unchanged(module, current, target, ("FilterType",), "CMQ topic")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                request = models.ModifyCmqTopicAttributeRequest()
                request.TopicName, request.MaxMsgSize = p["topic_name"], p["max_msg_size"]
                request.MsgRetentionSeconds, request.Trace = p["message_retention_seconds"], p["trace"]
                module.sdk_call(client.ModifyCmqTopicAttribute, request)
            else:
                request = models.CreateCmqTopicRequest()
                request.TopicName, request.MaxMsgSize = p["topic_name"], p["max_msg_size"]
                request.MsgRetentionSeconds, request.FilterType = p["message_retention_seconds"], p["filter_type"]
                request.Trace, request.Tags = p["trace"], tags(models, p["tags"])
                module.sdk_call(client.CreateCmqTopic, request)
            current = find(module, client, models, p["topic_name"])
        module.exit_json(changed=True, **(diff or {}), topic=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
