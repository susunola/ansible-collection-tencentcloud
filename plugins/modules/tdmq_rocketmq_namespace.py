#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tdmq_rocketmq_namespace
short_description: Manage TDMQ RocketMQ namespaces
version_added: "0.14.0"
description: Creates, updates and deletes a RocketMQ namespace in a TDMQ cluster.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, required: true, description: RocketMQ cluster ID.}
  name: {type: str, required: true, description: Namespace name.}
  remark: {type: str, default: '', description: Namespace remark.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmq_rocketmq_namespace:
    cluster_id: rocketmq-xxxxxxxx
    name: production
    remark: Production workloads
"""
RETURN = r"""namespace: {description: RocketMQ namespace metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client

    return models, tdmq_client


def describe_request(models, p, offset=0):
    request = models.DescribeRocketMQNamespacesRequest()
    request.ClusterId, request.Offset, request.Limit, request.NameKeyword = p["cluster_id"], offset, 100, p["name"]
    return request


def create_request(models, p):
    request = models.CreateRocketMQNamespaceRequest()
    request.ClusterId, request.NamespaceId, request.Remark = p["cluster_id"], p["name"], p["remark"]
    return request


def update_request(models, p):
    request = models.ModifyRocketMQNamespaceRequest()
    request.ClusterId, request.NamespaceId, request.Remark = p["cluster_id"], p["name"], p["remark"]
    return request


def delete_request(models, p):
    request = models.DeleteRocketMQNamespaceRequest()
    request.ClusterId, request.NamespaceId = p["cluster_id"], p["name"]
    return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeRocketMQNamespaces, describe_request(models, p, offset))
        items = list(response.Namespaces or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("NamespaceId") == p["name"]:
                return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            return None


def comparable(value):
    return {"NamespaceId": value.get("NamespaceId"), "Remark": value.get("Remark") or ""}


def desired(p):
    return {"NamespaceId": p["name"], "Remark": p["remark"]}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "cluster_id": {"required": True},
            "name": {"required": True},
            "remark": {"default": ""},
        },
        supports_check_mode=True,
    )
    p = module.params
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
                module.sdk_call(client.DeleteRocketMQNamespace, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), namespace=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, namespace=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            method = client.ModifyRocketMQNamespace if current else client.CreateRocketMQNamespace
            module.sdk_call(method, update_request(models, p) if current else create_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), namespace=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
