#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tdmq_rocketmq_group
short_description: Manage TDMQ RocketMQ consumer groups
version_added: "0.14.0"
description: Creates, updates and deletes a RocketMQ consumer group in a namespace.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, required: true, description: RocketMQ cluster ID.}
  namespace: {type: str, required: true, description: RocketMQ namespace.}
  name: {type: str, required: true, description: Consumer group name.}
  group_type: {type: str, choices: [TCP, HTTP], default: TCP, description: Immutable group protocol type.}
  read_enabled: {type: bool, default: true, description: Enable message consumption.}
  broadcast_enabled: {type: bool, default: false, description: Enable broadcast consumption.}
  retry_max_times: {type: int, default: 16, description: Maximum delivery retry count.}
  remark: {type: str, default: '', description: Consumer group remark.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmq_rocketmq_group:
    cluster_id: rocketmq-xxxxxxxx
    namespace: production
    name: order-workers
    retry_max_times: 12
"""
RETURN = r"""group: {description: RocketMQ consumer group metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client

    return models, tdmq_client


def describe_request(models, p, offset=0):
    request = models.DescribeRocketMQGroupsRequest()
    request.ClusterId, request.NamespaceId, request.Offset, request.Limit, request.FilterOneGroup = p["cluster_id"], p["namespace"], offset, 100, p["name"]
    return request


def create_request(models, p):
    request = models.CreateRocketMQGroupRequest()
    request.GroupId, request.Namespaces, request.ClusterId = p["name"], [p["namespace"]], p["cluster_id"]
    request.ReadEnable, request.BroadcastEnable, request.Remark = p["read_enabled"], p["broadcast_enabled"], p["remark"]
    request.GroupType, request.RetryMaxTimes = p["group_type"], p["retry_max_times"]
    return request


def update_request(models, p):
    request = models.ModifyRocketMQGroupRequest()
    request.ClusterId, request.NamespaceId, request.GroupId = p["cluster_id"], p["namespace"], p["name"]
    request.Remark, request.ReadEnable = p["remark"], p["read_enabled"]
    request.BroadcastEnable, request.RetryMaxTimes = p["broadcast_enabled"], p["retry_max_times"]
    return request


def delete_request(models, p):
    request = models.DeleteRocketMQGroupRequest()
    request.GroupId, request.NamespaceId, request.ClusterId = p["name"], p["namespace"], p["cluster_id"]
    return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeRocketMQGroups, describe_request(models, p, offset))
        items = list(response.Groups or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("Name") == p["name"]:
                return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            return None


def comparable(value):
    return {
        "Name": value.get("Name"),
        "GroupType": value.get("GroupType"),
        "ReadEnabled": bool(value.get("ReadEnabled")),
        "BroadcastEnabled": bool(value.get("BroadcastEnabled")),
        "RetryMaxTimes": int(value.get("RetryMaxTimes") or 0),
        "Remark": value.get("Remark") or "",
    }


def desired(p):
    return {
        "Name": p["name"],
        "GroupType": p["group_type"],
        "ReadEnabled": p["read_enabled"],
        "BroadcastEnabled": p["broadcast_enabled"],
        "RetryMaxTimes": p["retry_max_times"],
        "Remark": p["remark"],
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "cluster_id": {"required": True},
            "namespace": {"required": True},
            "name": {"required": True},
            "group_type": {"choices": ["TCP", "HTTP"], "default": "TCP"},
            "read_enabled": {"type": "bool", "default": True},
            "broadcast_enabled": {"type": "bool", "default": False},
            "retry_max_times": {"type": "int", "default": 16},
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
                module.exit_json(changed=False, group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteRocketMQGroup, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), group=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, group=current)
        diff = maybe_diff(module, before, target)
        if current:
            require_immutable_unchanged(module, before, target, ("GroupType",), "RocketMQ consumer group")
        if not module.check_mode:
            method = client.ModifyRocketMQGroup if current else client.CreateRocketMQGroup
            module.sdk_call(method, update_request(models, p) if current else create_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), group=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
