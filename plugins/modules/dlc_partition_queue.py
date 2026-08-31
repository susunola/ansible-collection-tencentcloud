#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: dlc_partition_queue
short_description: Manage Tencent Cloud DLC resource partition queues
version_added: "0.14.0"
description:
  - Creates, updates and deletes queues inside a DLC resource partition.
  - Resource usage is exact-set managed and guarded against accidental scale-down.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired lifecycle state.}
  partition_code: {type: str, required: true, description: Parent resource partition code.}
  name: {type: str, required: true, description: Exact queue name and immutable identity.}
  queue_type: {type: int, choices: [1, 2], description: Queue type, 1 dedicated or 2 shared.}
  description: {type: str, description: Queue description.}
  resource_usages:
    type: list
    elements: dict
    description: Exact resource type and usage ranges.
    options:
      resource_type: {type: str, required: true, description: DLC resource package type.}
      billing_item: {type: str, required: true, description: DLC billing item.}
      instance_type: {type: str, description: GPU machine type when applicable.}
      spec: {type: str, required: true, description: Resource specification string.}
      gpu_type: {type: str, description: GPU type when applicable.}
      min: {type: int, required: true, description: Minimum usage.}
      max: {type: int, required: true, description: Maximum usage.}
  allow_scale_down: {type: bool, default: false, description: Explicitly authorize removing or reducing resource ranges.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize queue deletion.}
  allow_delete_default: {type: bool, default: false, description: Explicitly authorize deleting a default queue.}
  wait: {type: bool, default: true, description: Wait for lifecycle and field convergence.}
  waiter_delay: {type: int, default: 5, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 300, description: Overall convergence timeout.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dlc_partition_queue:
    partition_code: rp-xxxxxxxx
    name: notebooks
    queue_type: 1
    description: Interactive analytics capacity
    resource_usages:
      - resource_type: CU
        billing_item: sv_dlc_standard_cu_standard_cu
        spec: '0:1:4:0'
        min: 32
        max: 128

- susunola.tencentcloud.dlc_partition_queue:
    partition_code: rp-xxxxxxxx
    name: notebooks
    state: absent
    allow_delete: true
'''
RETURN = r'''
queue:
  description: Effective DLC partition queue metadata.
  type: dict
  returned: always
queue_id:
  description: DLC partition queue ID.
  type: int
  returned: when present
'''

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client
    return models, dlc_client


def describe_request(models, partition_code, page=1):
    request = models.DescribePartitionQueuesRequest()
    request.PartitionCode, request.Page, request.PageSize = partition_code, page, 200
    return request


def _usage(value):
    result = []
    for item in value or []:
        spec = item.get("ResourceSpec", item.get("resource_spec", {})) or {}
        normalized = {
            "ResourceSpec": {
                "ResourceType": spec.get("ResourceType", item.get("resource_type")),
                "BillingItem": spec.get("BillingItem", item.get("billing_item")),
                "InstanceType": spec.get("InstanceType", item.get("instance_type")),
                "Spec": spec.get("Spec", item.get("spec")),
                "GpuType": spec.get("GpuType", item.get("gpu_type")),
            },
            "Min": item.get("Min", item.get("min")), "Max": item.get("Max", item.get("max")),
        }
        normalized["ResourceSpec"] = {k: v for k, v in normalized["ResourceSpec"].items() if v is not None}
        result.append(normalized)
    return sorted(result, key=lambda x: (x["ResourceSpec"].get("BillingItem", ""), x["ResourceSpec"].get("InstanceType", "")))


def normalize(value):
    result = dict(value or {}); result["ResourceUsage"] = _usage(result.get("ResourceUsage")); return result


def find(module, client, models, partition_code, name):
    page, matches = 1, []
    while True:
        response = module.sdk_call(client.DescribePartitionQueues, describe_request(models, partition_code, page))
        items = response.QueueList or []
        matches.extend(x._serialize(allow_none=True) for x in items if x.QueueName == name)
        if not items or page * 200 >= int(response.Total or 0): break
        page += 1
    if len(matches) > 1: module.fail_json(msg="Multiple DLC partition queues matched the exact name", partition_code=partition_code, name=name)
    return normalize(matches[0]) if matches else None


def payload(p, queue_id=None):
    result = {"PartitionCode": p["partition_code"], "QueueName": p["name"]}
    if queue_id is not None: result["Id"] = queue_id
    if p.get("description") is not None: result["Description"] = p["description"]
    if p.get("queue_type") is not None: result["QueueType"] = p["queue_type"]
    if p.get("resource_usages") is not None: result["ResourceUsages"] = _usage(p["resource_usages"])
    return result


def make_request(models, p, update=False, queue_id=None):
    request = models.ModifyPartitionQueueRequest() if update else models.CreatePartitionQueueRequest()
    request.from_json_string(json.dumps(payload(p, queue_id))); return request


def delete_request(models, p, queue_id):
    request = models.DeletePartitionQueueRequest()
    request.PartitionCode, request.QueueName, request.Id = p["partition_code"], p["name"], queue_id
    return request


def desired(p, current=None):
    result = dict(current or {}); result["QueueName"] = p["name"]
    if p.get("description") is not None: result["Description"] = p["description"]
    if p.get("queue_type") is not None: result["QueueType"] = p["queue_type"]
    if p.get("resource_usages") is not None: result["ResourceUsage"] = _usage(p["resource_usages"])
    return result


def drift(p, current):
    target, changes = desired(p, current), {}
    for source, key in (("description", "Description"), ("queue_type", "QueueType"), ("resource_usages", "ResourceUsage")):
        if p.get(source) is not None and current.get(key) != target.get(key): changes[key] = (current.get(key), target.get(key))
    return changes


def scale_down(old, new):
    def indexed(values):
        return {(x["ResourceSpec"].get("BillingItem"), x["ResourceSpec"].get("InstanceType")): x for x in values or []}
    before, after = indexed(old), indexed(new)
    if set(before) - set(after): return True
    return any(key in before and (item["Min"] < before[key]["Min"] or item["Max"] < before[key]["Max"]) for key, item in after.items())


def wait_queue(module, client, models, p, absent=False, expected=None):
    def poll():
        current = find(module, client, models, p["partition_code"], p["name"])
        if absent: return "absent" if current is None else "pending"
        if current is None: return "absent"
        if expected and any(current.get(k) != v for k, v in expected.items()): return "pending"
        return "ready"
    wait_for_state(module, poll, ["absent" if absent else "ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    usage_options = {
        "resource_type": {"required": True}, "billing_item": {"required": True}, "instance_type": {}, "spec": {"required": True},
        "gpu_type": {}, "min": {"type": "int", "required": True}, "max": {"type": "int", "required": True},
    }
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"}, "partition_code": {"required": True}, "name": {"required": True},
        "queue_type": {"type": "int", "choices": [1, 2]}, "description": {},
        "resource_usages": {"type": "list", "elements": "dict", "options": usage_options},
        "allow_scale_down": {"type": "bool", "default": False}, "allow_delete": {"type": "bool", "default": False},
        "allow_delete_default": {"type": "bool", "default": False}, "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5}, "waiter_timeout": {"type": "int", "default": 300},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True); p = module.params
    for item in p.get("resource_usages") or []:
        if item["min"] > item["max"]: module.fail_json(msg="resource usage min must not exceed max", resource_usage=item)
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["partition_code"], p["name"])
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, queue=None, queue_id=None)
            if not p["allow_delete"]: module.fail_json(msg="set allow_delete=true to authorize deleting the DLC partition queue", queue=current)
            if int(current.get("IsDefault") or 0) and not p["allow_delete_default"]: module.fail_json(msg="set allow_delete_default=true to authorize deleting a default DLC partition queue", queue=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeletePartitionQueue, delete_request(models, p, current["Id"]))
                if p["wait"]: wait_queue(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff_value or {}), queue=None, queue_id=None)
        if not current:
            missing = [key for key in ("queue_type", "resource_usages") if p.get(key) is None]
            if missing: module.fail_json(msg="creation parameters are required for a DLC partition queue", missing=missing)
            after, diff_value = desired(p), maybe_diff(module, None, desired(p)); queue_id = None
            if not module.check_mode:
                queue_id = module.sdk_call(client.CreatePartitionQueue, make_request(models, p)).Id
                if p["wait"]: wait_queue(module, client, models, p, expected={k: v for k, v in after.items() if k != "QueueName"})
                current = find(module, client, models, p["partition_code"], p["name"])
            module.exit_json(changed=True, **(diff_value or {}), queue=current if not module.check_mode else after, queue_id=(current or {}).get("Id") or queue_id)
        changes = drift(p, current)
        if "ResourceUsage" in changes and scale_down(*changes["ResourceUsage"]) and not p["allow_scale_down"]:
            module.fail_json(msg="set allow_scale_down=true to authorize reducing DLC queue resources", resource_usage_drift=changes["ResourceUsage"])
        if not changes: module.exit_json(changed=False, queue=current, queue_id=current.get("Id"))
        after, diff_value = desired(p, current), maybe_diff(module, current, desired(p, current))
        if not module.check_mode:
            module.sdk_call(client.ModifyPartitionQueue, make_request(models, p, update=True, queue_id=current["Id"]))
            if p["wait"]: wait_queue(module, client, models, p, expected={k: v[1] for k, v in changes.items()})
            current = find(module, client, models, p["partition_code"], p["name"])
        module.exit_json(changed=True, **(diff_value or {}), queue=current if not module.check_mode else after, queue_id=current.get("Id"))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
