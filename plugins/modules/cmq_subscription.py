#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cmq_subscription
short_description: Manage Tencent Cloud CMQ topic subscriptions
version_added: "0.14.0"
description: Creates, updates and deletes push subscriptions for a CMQ topic.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  topic_name: {type: str, required: true, description: Parent topic name.}
  subscription_name: {type: str, required: true, description: Subscription name.}
  protocol: {type: str, choices: [http, queue], default: http, description: Push protocol.}
  endpoint: {type: str, required: true, description: Push URL or queue name.}
  notify_strategy: {type: str, choices: [BACKOFF_RETRY, EXPONENTIAL_DECAY_RETRY], default: BACKOFF_RETRY, description: Retry strategy.}
  notify_content_format: {type: str, choices: [JSON, SIMPLIFIED], default: JSON, description: Push payload format.}
  filter_tags: {type: list, elements: str, default: [], description: Message filter tags.}
  binding_key: {type: list, elements: str, default: [], description: Routing binding keys.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cmq_subscription:
    topic_name: order-events
    subscription_name: order-webhook
    endpoint: https://example.com/events
'''
RETURN = r'''subscription: {description: Subscription metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client
    return models, tdmq_client


def find(module, client, models, topic, name):
    request = models.DescribeCmqSubscriptionDetailRequest()
    request.TopicName, request.Offset, request.Limit = topic, 0, 100
    response = module.sdk_call(client.DescribeCmqSubscriptionDetail, request)
    items = getattr(response, "SubscriptionSet", None) or []
    return next((x._serialize(allow_none=True) for x in items if x.SubscriptionName == name), None)


def target(p):
    return {"SubscriptionName": p["subscription_name"], "Protocol": p["protocol"], "Endpoint": p["endpoint"],
            "NotifyStrategy": p["notify_strategy"], "NotifyContentFormat": p["notify_content_format"],
            "FilterTags": sorted(p["filter_tags"]), "BindingKey": sorted(p["binding_key"])}


def current_fields(value):
    return {"SubscriptionName": value.get("SubscriptionName"), "Protocol": value.get("Protocol"),
            "Endpoint": value.get("Endpoint"), "NotifyStrategy": value.get("NotifyStrategy"),
            "NotifyContentFormat": value.get("NotifyContentFormat"),
            "FilterTags": sorted(value.get("FilterTags") or value.get("FilterTag") or []),
            "BindingKey": sorted(value.get("BindingKey") or [])}


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"}, "topic_name": {"required": True},
        "subscription_name": {"required": True}, "protocol": {"choices": ["http", "queue"], "default": "http"},
        "endpoint": {"required": True}, "notify_strategy": {"choices": ["BACKOFF_RETRY", "EXPONENTIAL_DECAY_RETRY"], "default": "BACKOFF_RETRY"},
        "notify_content_format": {"choices": ["JSON", "SIMPLIFIED"], "default": "JSON"},
        "filter_tags": {"type": "list", "elements": "str", "default": []},
        "binding_key": {"type": "list", "elements": "str", "default": []},
    }, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["topic_name"], p["subscription_name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, subscription=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteCmqSubscribeRequest()
                request.TopicName, request.SubscriptionName = p["topic_name"], p["subscription_name"]
                module.sdk_call(client.DeleteCmqSubscribe, request)
            module.exit_json(changed=True, **(diff or {}), subscription=current if module.check_mode else None)
        wanted, before = target(p), current_fields(current) if current else None
        if before == wanted:
            module.exit_json(changed=False, subscription=current)
        if current:
            require_immutable_unchanged(module, before, wanted, ("Protocol", "Endpoint"), "CMQ subscription")
        diff = maybe_diff(module, before, wanted)
        if not module.check_mode:
            if current:
                request = models.ModifyCmqSubscriptionAttributeRequest()
                request.TopicName, request.SubscriptionName = p["topic_name"], p["subscription_name"]
                request.NotifyStrategy, request.NotifyContentFormat = p["notify_strategy"], p["notify_content_format"]
                request.FilterTags, request.BindingKey = p["filter_tags"], p["binding_key"]
                module.sdk_call(client.ModifyCmqSubscriptionAttribute, request)
            else:
                request = models.CreateCmqSubscribeRequest()
                request.TopicName, request.SubscriptionName = p["topic_name"], p["subscription_name"]
                request.Protocol, request.Endpoint = p["protocol"], p["endpoint"]
                request.NotifyStrategy, request.NotifyContentFormat = p["notify_strategy"], p["notify_content_format"]
                request.FilterTag, request.BindingKey = p["filter_tags"], p["binding_key"]
                module.sdk_call(client.CreateCmqSubscribe, request)
            current = find(module, client, models, p["topic_name"], p["subscription_name"])
        module.exit_json(changed=True, **(diff or {}), subscription=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
