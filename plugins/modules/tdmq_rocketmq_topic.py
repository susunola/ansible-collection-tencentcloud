#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tdmq_rocketmq_topic
short_description: Manage TDMQ RocketMQ topics
version_added: "0.14.0"
description: Creates, updates and deletes a RocketMQ topic in a namespace.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, required: true, description: RocketMQ cluster ID.}
  namespace: {type: str, required: true, description: RocketMQ namespace.}
  name: {type: str, required: true, description: Topic name.}
  topic_type: {type: str, choices: [Normal, GlobalOrder, PartitionedOrder, Transaction, DelayScheduled], default: Normal, description: Immutable topic type.}
  partition_num: {type: int, default: 1, description: Number of read and write partitions.}
  remark: {type: str, default: '', description: Topic remark.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmq_rocketmq_topic:
    cluster_id: rocketmq-xxxxxxxx
    namespace: production
    name: orders
    topic_type: PartitionedOrder
    partition_num: 6
"""
RETURN = r"""topic: {description: RocketMQ topic metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client

    return models, tdmq_client


def describe_request(models, p, offset=0):
    request = models.DescribeRocketMQTopicsRequest()
    request.ClusterId, request.NamespaceId, request.Offset, request.Limit, request.FilterName = p["cluster_id"], p["namespace"], offset, 100, p["name"]
    return request


def create_request(models, p):
    request = models.CreateRocketMQTopicRequest()
    request.Topic, request.Namespaces, request.Type, request.ClusterId = p["name"], [p["namespace"]], p["topic_type"], p["cluster_id"]
    request.Remark, request.PartitionNum = p["remark"], p["partition_num"]
    return request


def update_request(models, p):
    request = models.ModifyRocketMQTopicRequest()
    request.ClusterId, request.NamespaceId, request.Topic = p["cluster_id"], p["namespace"], p["name"]
    request.Remark, request.PartitionNum = p["remark"], p["partition_num"]
    return request


def delete_request(models, p):
    request = models.DeleteRocketMQTopicRequest()
    request.Topic, request.NamespaceId, request.ClusterId = p["name"], p["namespace"], p["cluster_id"]
    return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeRocketMQTopics, describe_request(models, p, offset))
        items = list(response.Topics or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("Name") == p["name"]:
                return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            return None


def comparable(value):
    return {"Name": value.get("Name"), "Type": value.get("Type"), "PartitionNum": int(value.get("PartitionNum") or 0), "Remark": value.get("Remark") or ""}


def desired(p):
    return {"Name": p["name"], "Type": p["topic_type"], "PartitionNum": p["partition_num"], "Remark": p["remark"]}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "cluster_id": {"required": True},
            "namespace": {"required": True},
            "name": {"required": True},
            "topic_type": {"choices": ["Normal", "GlobalOrder", "PartitionedOrder", "Transaction", "DelayScheduled"], "default": "Normal"},
            "partition_num": {"type": "int", "default": 1},
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
                module.exit_json(changed=False, topic=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteRocketMQTopic, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), topic=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, topic=current)
        diff = maybe_diff(module, before, target)
        if current:
            require_immutable_unchanged(module, before, target, ("Type",), "RocketMQ topic")
            if target["PartitionNum"] < before["PartitionNum"]:
                module.fail_json(msg="RocketMQ topic partition_num cannot be decreased")
        if not module.check_mode:
            method = client.ModifyRocketMQTopic if current else client.CreateRocketMQTopic
            module.sdk_call(method, update_request(models, p) if current else create_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), topic=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
