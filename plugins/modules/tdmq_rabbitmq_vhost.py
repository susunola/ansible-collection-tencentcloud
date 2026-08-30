#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: tdmq_rabbitmq_vhost
short_description: Manage TDMQ RabbitMQ virtual hosts
version_added: "0.14.0"
description: Creates, updates and deletes RabbitMQ virtual hosts, including message tracing and initial mirror policy.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: TDMQ RabbitMQ instance ID.}
  name: {type: str, required: true, description: Virtual host name.}
  description: {type: str, default: '', description: Virtual host description.}
  trace_enabled: {type: bool, default: false, description: Enable message tracing.}
  mirror_queue_policy: {type: bool, default: true, description: Immutable initial mirror queue policy.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdmq_rabbitmq_vhost:
    instance_id: amqp-xxxxxxxx
    name: production
    description: Production workloads
    trace_enabled: true
'''
RETURN = r'''virtual_host: {description: RabbitMQ virtual host metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client
    return models, tdmq_client


def describe_request(models, p, offset=0):
    request = models.DescribeRabbitMQVirtualHostRequest(); request.InstanceId, request.VirtualHost, request.Offset, request.Limit = p["instance_id"], p["name"], offset, 100; return request


def create_request(models, p):
    request = models.CreateRabbitMQVirtualHostRequest(); request.InstanceId, request.VirtualHost = p["instance_id"], p["name"]
    request.Description, request.TraceFlag, request.MirrorQueuePolicyFlag = p["description"], p["trace_enabled"], p["mirror_queue_policy"]; return request


def update_request(models, p):
    request = models.ModifyRabbitMQVirtualHostRequest(); request.InstanceId, request.VirtualHost = p["instance_id"], p["name"]
    request.Description, request.TraceFlag = p["description"], p["trace_enabled"]; return request


def delete_request(models, p):
    request = models.DeleteRabbitMQVirtualHostRequest(); request.InstanceId, request.VirtualHost = p["instance_id"], p["name"]; return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeRabbitMQVirtualHost, describe_request(models, p, offset)); items = list(response.VirtualHostList or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("VirtualHost") == p["name"]: return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0): return None


def comparable(value):
    return {"VirtualHost": value.get("VirtualHost"), "Description": value.get("Description") or "", "TraceFlag": bool(value.get("TraceFlag")), "MirrorQueuePolicyFlag": bool(value.get("MirrorQueuePolicyFlag"))}


def desired(p):
    return {"VirtualHost": p["name"], "Description": p["description"], "TraceFlag": p["trace_enabled"], "MirrorQueuePolicyFlag": p["mirror_queue_policy"]}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "name": {"required": True}, "description": {"default": ""}, "trace_enabled": {"type": "bool", "default": False}, "mirror_queue_policy": {"type": "bool", "default": True}}, supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, virtual_host=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteRabbitMQVirtualHost, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), virtual_host=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target: module.exit_json(changed=False, virtual_host=current)
        diff = maybe_diff(module, before, target)
        if current: require_immutable_unchanged(module, before, target, ("MirrorQueuePolicyFlag",), "RabbitMQ virtual host")
        if not module.check_mode:
            module.sdk_call(client.ModifyRabbitMQVirtualHost if current else client.CreateRabbitMQVirtualHost, update_request(models, p) if current else create_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), virtual_host=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
