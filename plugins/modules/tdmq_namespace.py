#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tdmq_namespace
short_description: Manage Tencent Cloud TDMQ Pulsar namespaces
version_added: "0.14.0"
description: Creates, updates and deletes Pulsar namespaces including retention and subscription lifecycle policies.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, required: true, description: Pulsar cluster ID.}
  name: {type: str, required: true, description: Namespace name.}
  message_ttl: {type: int, default: 86400, description: Unconsumed message TTL in seconds.}
  remark: {type: str, default: '', description: Namespace remark.}
  retention_minutes: {type: int, default: 0, description: Retained message duration in minutes.}
  retention_size_mb: {type: int, default: 0, description: Retained message size in MiB.}
  auto_subscription_creation: {type: bool, default: false, description: Automatically create missing subscriptions.}
  subscription_expiration_enabled: {type: bool, default: false, description: Automatically clean inactive subscriptions.}
  subscription_expiration_time: {type: int, default: 0, description: Inactive subscription expiration time.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmq_namespace:
    cluster_id: pulsar-xxxxxxxx
    name: production
    message_ttl: 604800
    retention_minutes: 1440
    retention_size_mb: 10240
"""
RETURN = r"""namespace: {description: TDMQ Pulsar namespace metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client

    return models, tdmq_client


def retention(models, p):
    value = models.RetentionPolicy()
    value.TimeInMinutes, value.SizeInMB = p["retention_minutes"], p["retention_size_mb"]
    return value


def describe_request(models, p, offset=0):
    request = models.DescribeEnvironmentsRequest()
    request.ClusterId, request.EnvironmentId, request.Offset, request.Limit = p["cluster_id"], p["name"], offset, 20
    return request


def apply_request(request, models, p):
    request.EnvironmentId, request.ClusterId, request.MsgTTL, request.Remark = p["name"], p["cluster_id"], p["message_ttl"], p["remark"]
    request.RetentionPolicy, request.AutoSubscriptionCreation = retention(models, p), p["auto_subscription_creation"]
    request.SubscriptionExpirationTimeEnable, request.SubscriptionExpirationTime = p["subscription_expiration_enabled"], p["subscription_expiration_time"]
    return request


def create_request(models, p):
    return apply_request(models.CreateEnvironmentRequest(), models, p)


def update_request(models, p):
    return apply_request(models.ModifyEnvironmentAttributesRequest(), models, p)


def delete_request(models, p):
    request = models.DeleteEnvironmentsRequest()
    request.ClusterId, request.EnvironmentIds = p["cluster_id"], [p["name"]]
    return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeEnvironments, describe_request(models, p, offset))
        items = list(response.EnvironmentSet or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("EnvironmentId") == p["name"] or value.get("NamespaceName") == p["name"]:
                return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            return None


def normalize(value):
    policy = value.get("RetentionPolicy") or {}
    return {
        "EnvironmentId": value.get("EnvironmentId") or value.get("NamespaceName"),
        "MsgTTL": value.get("MsgTTL"),
        "Remark": value.get("Remark") or "",
        "RetentionMinutes": policy.get("TimeInMinutes") or 0,
        "RetentionSizeMB": policy.get("SizeInMB") or 0,
        "AutoSubscriptionCreation": bool(value.get("AutoSubscriptionCreation")),
        "SubscriptionExpirationTimeEnable": bool(value.get("SubscriptionExpirationTimeEnable")),
        "SubscriptionExpirationTime": value.get("SubscriptionExpirationTime") or 0,
    }


def desired(p):
    return {
        "EnvironmentId": p["name"],
        "MsgTTL": p["message_ttl"],
        "Remark": p["remark"],
        "RetentionMinutes": p["retention_minutes"],
        "RetentionSizeMB": p["retention_size_mb"],
        "AutoSubscriptionCreation": p["auto_subscription_creation"],
        "SubscriptionExpirationTimeEnable": p["subscription_expiration_enabled"],
        "SubscriptionExpirationTime": p["subscription_expiration_time"],
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "cluster_id": {"required": True},
            "name": {"required": True},
            "message_ttl": {"type": "int", "default": 86400},
            "remark": {"default": ""},
            "retention_minutes": {"type": "int", "default": 0},
            "retention_size_mb": {"type": "int", "default": 0},
            "auto_subscription_creation": {"type": "bool", "default": False},
            "subscription_expiration_enabled": {"type": "bool", "default": False},
            "subscription_expiration_time": {"type": "int", "default": 0},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["message_ttl"] < 60 or p["message_ttl"] > 1296000:
        module.fail_json(msg="message_ttl must be between 60 and 1296000 seconds")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, namespace=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteEnvironments, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), namespace=current if module.check_mode else None)
        target, before = desired(p), normalize(current) if current else None
        if before == target:
            module.exit_json(changed=False, namespace=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(
                client.ModifyEnvironmentAttributes if current else client.CreateEnvironment, update_request(models, p) if current else create_request(models, p)
            )
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), namespace=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
