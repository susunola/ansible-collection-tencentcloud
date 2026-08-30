#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: trabbit_serverless_vhost
short_description: Manage Tencent Cloud RabbitMQ Serverless virtual hosts
version_added: "0.14.0"
description: Creates, updates and deletes RabbitMQ Serverless virtual hosts.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: RabbitMQ Serverless instance ID.}
  name: {type: str, required: true, description: Virtual-host name.}
  description: {type: str, default: '', description: Virtual-host description.}
  mirror_queue_policy: {type: bool, default: true, description: Immutable initial mirror-queue policy.}
  trace_enabled: {type: bool, description: Message tracing value used during creation or an explicit trace update.}
  apply_trace: {type: bool, default: false, description: Explicitly write trace_enabled because the service does not return its current value.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.trabbit_serverless_vhost:
    instance_id: amqp-xxxxxxxx
    name: production
    description: Production workloads
    mirror_queue_policy: true
'''
RETURN = r'''virtual_host: {description: RabbitMQ Serverless virtual-host metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.trabbit.v20230418 import models, trabbit_client
    return models, trabbit_client
def describe_request(models, p, offset=0):
    r = models.DescribeRabbitMQServerlessVirtualHostRequest(); r.InstanceId, r.VirtualHost, r.Offset, r.Limit = p["instance_id"], p["name"], offset, 100; return r
def create_request(models, p):
    r = models.CreateRabbitMQServerlessVirtualHostRequest(); r.InstanceId, r.VirtualHost, r.Description = p["instance_id"], p["name"], p["description"]; r.TraceFlag = p.get("trace_enabled") if p.get("trace_enabled") is not None else False; r.MirrorQueuePolicyFlag = p["mirror_queue_policy"]; return r
def update_request(models, p):
    r = models.ModifyRabbitMQServerlessVirtualHostRequest(); r.InstanceId, r.VirtualHost, r.Description = p["instance_id"], p["name"], p["description"]; r.TraceFlag = p.get("trace_enabled") if p["apply_trace"] else None; return r
def delete_request(models, p):
    r = models.DeleteRabbitMQServerlessVirtualHostRequest(); r.InstanceId, r.VirtualHost = p["instance_id"], p["name"]; return r
def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeRabbitMQServerlessVirtualHost, describe_request(models, p, offset)); items = list(response.VirtualHostList or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("VirtualHost") == p["name"]: return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0): return None
def comparable(value): return {"VirtualHost": value.get("VirtualHost"), "Description": value.get("Description") or "", "MirrorQueuePolicyFlag": bool(value.get("MirrorQueuePolicyFlag"))}
def desired(p): return {"VirtualHost": p["name"], "Description": p["description"], "MirrorQueuePolicyFlag": p["mirror_queue_policy"]}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "name": {"required": True}, "description": {"default": ""}, "mirror_queue_policy": {"type": "bool", "default": True}, "trace_enabled": {"type": "bool"}, "apply_trace": {"type": "bool", "default": False}}, required_if=[("apply_trace", True, ["trace_enabled"])], supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TrabbitClient, "trabbit.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, virtual_host=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteRabbitMQServerlessVirtualHost, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), virtual_host=current if module.check_mode else None)
        before, target = comparable(current) if current else None, desired(p)
        if before == target and not p["apply_trace"]: module.exit_json(changed=False, virtual_host=current)
        diff = maybe_diff(module, before, target)
        if current: require_immutable_unchanged(module, before, target, ("MirrorQueuePolicyFlag",), "RabbitMQ Serverless virtual host")
        if not module.check_mode:
            module.sdk_call(client.ModifyRabbitMQServerlessVirtualHost if current else client.CreateRabbitMQServerlessVirtualHost, update_request(models, p) if current else create_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), virtual_host=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
