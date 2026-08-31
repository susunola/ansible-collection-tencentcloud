#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: gwlb_target_group_instances
short_description: Reconcile Tencent Cloud GWLB target group instances
version_added: "0.14.0"
description: Registers, updates and deregisters GWLB backend appliance IPs using exact-set or additive reconciliation.
options:
  target_group_id: {type: str, required: true, description: Target group ID.}
  instances:
    type: list
    elements: dict
    default: []
    description: Desired backend appliance endpoints.
    suboptions:
      ip: {type: str, required: true, description: Backend bind IP.}
      port: {type: int, default: 6081, description: Backend GENEVE port.}
      weight: {type: int, default: 10, description: Backend weight.}
  purge: {type: bool, default: true, description: Deregister endpoints not listed.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.gwlb_target_group_instances:
    target_group_id: lbtg-xxxxxxxx
    instances:
      - {ip: 10.0.1.10, port: 6081, weight: 50}
      - {ip: 10.0.1.11, port: 6081, weight: 50}
"""
RETURN = r"""instances: {description: Effective GWLB backend instances., type: list, elements: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.gwlb.v20240906 import models, gwlb_client

    return models, gwlb_client


def describe_request(models, target_group_id):
    r = models.DescribeTargetGroupInstancesRequest()
    r.Offset, r.Limit = 0, 100
    f = models.Filter()
    f.Name, f.Values = "TargetGroupId", [target_group_id]
    r.Filters = [f]
    return r


def _items(models, values):
    result = []
    for value in values:
        x = models.TargetGroupInstance()
        x.BindIP, x.Port, x.Weight = value["ip"], value["port"], value.get("weight", 10)
        result.append(x)
    return result


def register_request(models, p, values):
    r = models.RegisterTargetGroupInstancesRequest()
    r.TargetGroupId, r.TargetGroupInstances = p["target_group_id"], _items(models, values)
    return r


def weight_request(models, p, values):
    r = models.ModifyTargetGroupInstancesWeightRequest()
    r.TargetGroupId, r.TargetGroupInstances = p["target_group_id"], _items(models, values)
    return r


def deregister_request(models, p, values):
    r = models.DeregisterTargetGroupInstancesRequest()
    r.TargetGroupId, r.TargetGroupInstances = p["target_group_id"], _items(models, values)
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeTargetGroupInstances, describe_request(models, p["target_group_id"]))
    return sorted([{"ip": x.BindIP, "port": x.Port, "weight": x.Weight} for x in response.TargetGroupInstanceSet or []], key=lambda x: (x["ip"], x["port"]))


def normalized(values):
    return sorted([{"ip": x["ip"], "port": x.get("port", 6081), "weight": x.get("weight", 10)} for x in values], key=lambda x: (x["ip"], x["port"]))


def run_module():
    spec = {
        "target_group_id": {"required": True},
        "instances": {
            "type": "list",
            "elements": "dict",
            "default": [],
            "options": {"ip": {"required": True}, "port": {"type": "int", "default": 6081}, "weight": {"type": "int", "default": 10}},
        },
        "purge": {"type": "bool", "default": True},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.GwlbClient, "gwlb.tencentcloudapi.com")
    try:
        current, wanted = find(module, client, models, p), normalized(p["instances"])
        old = {(x["ip"], x["port"]): x for x in current}
        new = {(x["ip"], x["port"]): x for x in wanted}
        additions = [x for k, x in new.items() if k not in old]
        updates = [x for k, x in new.items() if k in old and old[k]["weight"] != x["weight"]]
        removals = [x for k, x in old.items() if p["purge"] and k not in new]
        merged = dict(old)
        merged.update(new)
        effective = wanted if p["purge"] else normalized(list(merged.values()))
        if not additions and not updates and not removals:
            module.exit_json(changed=False, instances=current)
        diff = maybe_diff(module, current, effective)
        if not module.check_mode:
            if additions:
                module.sdk_call(client.RegisterTargetGroupInstances, register_request(models, p, additions))
            if updates:
                module.sdk_call(client.ModifyTargetGroupInstancesWeight, weight_request(models, p, updates))
            if removals:
                module.sdk_call(client.DeregisterTargetGroupInstances, deregister_request(models, p, removals))
            effective = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), instances=effective)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
