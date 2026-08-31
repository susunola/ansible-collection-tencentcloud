#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdwdoris_workload_group
short_description: Manage Tencent Cloud CDW Doris workload groups
version_added: "0.14.0"
description:
  - Creates, updates and deletes a named Doris workload group.
  - Optionally reconciles the instance-wide workload-group switch.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: CDW Doris instance ID.}
  name: {type: str, required: true, description: Workload group name.}
  cpu_share: {type: int, description: Relative CPU weight.}
  memory_limit: {type: int, description: Memory percentage limit.}
  enable_memory_overcommit: {type: bool, description: Allow memory overcommit.}
  cpu_hard_limit: {type: str, description: CPU hard limit accepted by the Doris API.}
  min_cpu_percent: {type: int, description: Minimum reserved CPU percentage on Doris 4.1 or later.}
  min_memory_percent: {type: int, description: Minimum reserved memory percentage on Doris 4.1 or later.}
  max_concurrency: {type: int, description: Maximum concurrent queries.}
  max_queue_size: {type: int, description: Maximum queued queries.}
  queue_timeout: {type: int, description: Queue timeout in milliseconds.}
  workload_groups_enabled: {type: bool, description: Desired instance-wide workload-group switch.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cdwdoris_workload_group:
    instance_id: cdwdoris-xxxxxxxx
    name: interactive
    cpu_share: 800
    memory_limit: 40
    max_concurrency: 30
    max_queue_size: 15
    queue_timeout: 5000
    workload_groups_enabled: true
'''
RETURN = r'''workload_group: {description: Effective workload group., type: dict, returned: always}
workload_groups_status: {description: Instance-wide workload-group status., type: str, returned: always}'''

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload

FIELDS = {
    "cpu_share": "CpuShare", "memory_limit": "MemoryLimit",
    "enable_memory_overcommit": "EnableMemoryOverCommit", "cpu_hard_limit": "CpuHardLimit",
    "min_cpu_percent": "MinCpuPercent", "min_memory_percent": "MinMemoryPercent",
    "max_concurrency": "MaxConcurrencyNum", "max_queue_size": "MaxQueueSize",
    "queue_timeout": "QueueTimeout",
}


def _load():
    from tencentcloud.cdwdoris.v20211228 import models, cdwdoris_client
    return models, cdwdoris_client


def desired(params):
    value = {"WorkloadGroupName": params["name"]}
    value.update({sdk: params[key] for key, sdk in FIELDS.items() if params.get(key) is not None})
    return value


def comparable(value, target):
    return {key: value.get(key) for key in target}


def describe(module, client, models, instance_id):
    request = models.DescribeWorkloadGroupRequest(); request.InstanceId = instance_id
    response = module.sdk_call(client.DescribeWorkloadGroup, request)
    if response.ErrorMsg:
        module.fail_json(msg=response.ErrorMsg)
    groups = [item._serialize(allow_none=True) for item in response.WorkloadGroups or []]
    return groups, response.Status


def group_request(models, params):
    request = models.CreateWorkloadGroupRequest(); request.InstanceId = params["instance_id"]
    request.WorkloadGroup = models.WorkloadGroupConfig(); request.WorkloadGroup.from_json_string(json.dumps(desired(params)))
    return request


def update_payload(current, target):
    managed_fields = {"WorkloadGroupName"}.union(FIELDS.values())
    value = {key: current.get(key) for key in managed_fields if current.get(key) is not None}
    value.update(target)
    return value


def update_request(models, instance_id, payload):
    request = models.ModifyWorkloadGroupRequest(); request.InstanceId = instance_id
    request.WorkloadGroup = models.WorkloadGroupConfig(); request.WorkloadGroup.from_json_string(json.dumps(payload))
    return request


def delete_request(models, params):
    request = models.DeleteWorkloadGroupRequest(); request.InstanceId = params["instance_id"]; request.WorkloadGroupName = params["name"]
    return request


def status_request(models, instance_id, enabled):
    request = models.ModifyWorkloadGroupStatusRequest(); request.InstanceId = instance_id; request.OperationType = "open" if enabled else "close"
    return request


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {"required": True}, "name": {"required": True},
        "cpu_share": {"type": "int"}, "memory_limit": {"type": "int"},
        "enable_memory_overcommit": {"type": "bool"}, "cpu_hard_limit": {},
        "min_cpu_percent": {"type": "int"}, "min_memory_percent": {"type": "int"},
        "max_concurrency": {"type": "int"}, "max_queue_size": {"type": "int"},
        "queue_timeout": {"type": "int"}, "workload_groups_enabled": {"type": "bool"},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    params = module.params; module.require_sdk(); models, client_module = _load()
    client = module.create_client(client_module.CdwdorisClient, "cdwdoris.tencentcloudapi.com")
    try:
        groups, current_status = describe(module, client, models, params["instance_id"])
        matches = [item for item in groups if item.get("WorkloadGroupName") == params["name"]]
        if len(matches) > 1:
            module.fail_json(msg="Multiple CDW Doris workload groups matched", name=params["name"])
        current = matches[0] if matches else None
        desired_status = None if params.get("workload_groups_enabled") is None else ("open" if params["workload_groups_enabled"] else "close")
        status_changed = desired_status is not None and desired_status != current_status
        if params["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, workload_group=None, workload_groups_status=current_status)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                response = module.sdk_call(client.DeleteWorkloadGroup, delete_request(models, params))
                if response.ErrorMsg: module.fail_json(msg=response.ErrorMsg)
            module.exit_json(changed=True, **(diff or {}), workload_group=None, workload_groups_status=current_status)
        target = desired(params)
        group_changed = current is None or comparable(current, target) != target
        diff = maybe_diff(module, comparable(current or {}, target) if current else None, target)
        if not module.check_mode:
            if current is None:
                response = module.sdk_call(client.CreateWorkloadGroup, group_request(models, params))
            elif group_changed:
                response = module.sdk_call(client.ModifyWorkloadGroup, update_request(models, params["instance_id"], update_payload(current, target)))
            else:
                response = None
            if response is not None and response.ErrorMsg: module.fail_json(msg=response.ErrorMsg)
            if status_changed:
                response = module.sdk_call(client.ModifyWorkloadGroupStatus, status_request(models, params["instance_id"], params["workload_groups_enabled"]))
                if response.ErrorMsg: module.fail_json(msg=response.ErrorMsg)
            groups, current_status = describe(module, client, models, params["instance_id"])
            current = next((item for item in groups if item.get("WorkloadGroupName") == params["name"]), target)
        module.exit_json(changed=group_changed or status_changed, **(diff or {}), workload_group=current if not module.check_mode else target, workload_groups_status=desired_status or current_status)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
