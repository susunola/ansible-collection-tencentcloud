#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: alb_target_group_targets
short_description: Reconcile Tencent Cloud ALB target group backends
version_added: "0.14.0"
description: Adds, updates and removes ALB backend targets using exact-set or additive reconciliation.
options:
  target_group_id: {type: str, required: true, description: Target group ID.}
  targets:
    type: list
    elements: dict
    default: []
    description: Desired backend targets.
    suboptions:
      ip: {type: str, required: true, description: Backend ENI IP address.}
      port: {type: int, required: true, description: Backend service port.}
      weight: {type: int, default: 10, description: Backend weight from 0 to 100.}
  purge: {type: bool, default: true, description: Remove backends not listed in targets.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.alb_target_group_targets:
    target_group_id: alb-tg-xxxxxxxx
    targets:
      - {ip: 10.0.1.10, port: 8080, weight: 50}
      - {ip: 10.0.1.11, port: 8080, weight: 50}
'''
RETURN = r'''targets: {description: Effective ALB backend targets., type: list, elements: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.alb.v20251030 import models, alb_client
    return models, alb_client
def describe_request(models, target_group_id):
    r = models.DescribeTargetGroupTargetsRequest(); r.TargetGroupId, r.MaxResults = target_group_id, 100; return r
def _target(models, cls, value):
    x = cls(); x.TargetIp, x.Port = value["ip"], value["port"]
    if hasattr(x, "Weight"): x.Weight = value.get("weight", 10)
    return x
def add_request(models, p, values):
    r = models.AddTargetsToTargetGroupRequest(); r.TargetGroupId = p["target_group_id"]; r.Targets = [_target(models, models.TargetToAdd, x) for x in values]; return r
def update_request(models, p, values):
    r = models.ModifyTargetsInTargetGroupRequest(); r.TargetGroupId = p["target_group_id"]; r.Targets = [_target(models, models.TargetToModify, x) for x in values]; return r
def remove_request(models, p, values):
    r = models.RemoveTargetsFromTargetGroupRequest(); r.TargetGroupId = p["target_group_id"]; r.Targets = [_target(models, models.TargetToRemove, x) for x in values]; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeTargetGroupTargets, describe_request(models, p["target_group_id"])); return sorted([{"ip": x.TargetIp, "port": x.Port, "weight": x.Weight} for x in response.Targets or []], key=lambda x: (x["ip"], x["port"]))
def normalized(values): return sorted([{"ip": x["ip"], "port": x["port"], "weight": x.get("weight", 10)} for x in values], key=lambda x: (x["ip"], x["port"]))
def run_module():
    spec = {"target_group_id": {"required": True}, "targets": {"type": "list", "elements": "dict", "default": [], "options": {"ip": {"required": True}, "port": {"type": "int", "required": True}, "weight": {"type": "int", "default": 10}}}, "purge": {"type": "bool", "default": True}}
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.AlbClient, "alb.tencentcloudapi.com")
    try:
        current, wanted = find(module, client, models, p), normalized(p["targets"]); old = {(x["ip"], x["port"]): x for x in current}; new = {(x["ip"], x["port"]): x for x in wanted}
        additions = [x for k, x in new.items() if k not in old]; updates = [x for k, x in new.items() if k in old and old[k]["weight"] != x["weight"]]; removals = [x for k, x in old.items() if p["purge"] and k not in new]
        merged = dict(old); merged.update(new)
        effective = wanted if p["purge"] else normalized(list(merged.values()))
        if not additions and not updates and not removals: module.exit_json(changed=False, targets=current)
        diff = maybe_diff(module, current, effective)
        if not module.check_mode:
            if additions: module.sdk_call(client.AddTargetsToTargetGroup, add_request(models, p, additions))
            if updates: module.sdk_call(client.ModifyTargetsInTargetGroup, update_request(models, p, updates))
            if removals: module.sdk_call(client.RemoveTargetsFromTargetGroup, remove_request(models, p, removals))
            effective = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), targets=effective)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__ == "__main__": main()
