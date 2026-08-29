#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tdmq_subscription
short_description: Manage Tencent Cloud TDMQ Pulsar subscriptions
version_added: "0.14.0"
description: Creates, updates and deletes subscriptions for TDMQ Pulsar topics.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  cluster_id: {description: Pulsar cluster ID., type: str, required: true}
  environment_id: {description: Pulsar namespace name., type: str, required: true}
  topic_name: {description: Parent topic name., type: str, required: true}
  name: {description: Subscription name., type: str, required: true}
  remark: {description: Subscription remark., type: str, default: ''}
  idempotent: {description: Enable broker-side idempotency., type: bool, default: true}
  auto_create_policy_topic: {description: Automatically create retry and dead-letter policy topics., type: bool, default: true}
  force: {description: Force deletion even when consumers are connected., type: bool, default: false}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdmq_subscription:
    cluster_id: pulsar-xxxxxxxx
    environment_id: production
    topic_name: orders
    name: order-workers
'''
RETURN = r'''subscription: {description: Subscription metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client
    return models, tdmq_client


def describe_request(models, p, offset=0):
    request = models.DescribeSubscriptionsRequest()
    request.ClusterId, request.EnvironmentId, request.TopicName = p["cluster_id"], p["environment_id"], p["topic_name"]
    request.SubscriptionName, request.Offset, request.Limit = p["name"], offset, 100
    return request


def find(module, client, models, p):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeSubscriptions, describe_request(models, p, offset))
        items = list(response.SubscriptionSets or [])
        matches.extend(x._serialize(allow_none=True) for x in items if x.SubscriptionName == p["name"])
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TDMQ subscriptions have the requested name", name=p["name"])
    return matches[0] if matches else None


def delete_request(models, p):
    request = models.DeleteSubscriptionsRequest()
    item = models.SubscriptionTopic()
    item.EnvironmentId, item.TopicName, item.SubscriptionName = p["environment_id"], p["topic_name"], p["name"]
    request.SubscriptionTopicSets, request.ClusterId = [item], p["cluster_id"]
    request.EnvironmentId, request.Force = p["environment_id"], p["force"]
    return request


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"},
        "cluster_id": {"required": True}, "environment_id": {"required": True},
        "topic_name": {"required": True}, "name": {"required": True}, "remark": {"default": ""},
        "idempotent": {"type": "bool", "default": True},
        "auto_create_policy_topic": {"type": "bool", "default": True},
        "force": {"type": "bool", "default": False},
    }, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, subscription=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteSubscriptions, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), subscription=current if module.check_mode else None)
        wanted = {"Remark": p["remark"]}
        if current and current.get("Remark", "") == p["remark"]:
            module.exit_json(changed=False, subscription=current)
        if current:
            module.fail_json(msg="TDMQ does not expose a Pulsar subscription update API; recreate it to change remark", subscription=current)
        diff = maybe_diff(module, None, wanted)
        if not module.check_mode:
            request = models.CreateSubscriptionRequest()
            request.ClusterId, request.EnvironmentId, request.TopicName = p["cluster_id"], p["environment_id"], p["topic_name"]
            request.SubscriptionName, request.Remark = p["name"], p["remark"]
            request.IsIdempotent, request.AutoCreatePolicyTopic = p["idempotent"], p["auto_create_policy_topic"]
            module.sdk_call(client.CreateSubscription, request)
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), subscription=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
