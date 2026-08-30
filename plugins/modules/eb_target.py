#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: eb_target
short_description: Manage Tencent Cloud EventBridge rule targets
version_added: "0.14.0"
description: Creates, updates and deletes delivery targets attached to EventBridge rules.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  event_bus_id: {type: str, required: true, description: Event bus ID.}
  rule_id: {type: str, required: true, description: Rule ID.}
  target_id: {type: str, description: Existing target ID.}
  target_type: {type: str, description: Target service type; immutable after creation.}
  target_description: {type: dict, description: SDK TargetDescription payload; immutable after creation.}
  enable_batch_delivery: {type: bool, description: Enable batched event delivery.}
  batch_timeout: {type: int, description: Maximum batch wait in seconds.}
  batch_event_count: {type: int, description: Maximum events per batch.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.eb_target:
    event_bus_id: eb-l8q2xxxx
    rule_id: rule-4y4xxxx
    target_type: scf
    target_description:
      ResourceDescription: '{"Region":"ap-guangzhou","Namespace":"default","FunctionName":"consume"}'
'''
RETURN = r'''target: {description: Effective EventBridge target metadata., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.eb.v20210416 import models, eb_client
    return models, eb_client
def _model(cls, value):
    if value is None: return None
    item = cls(); item.from_json_string(json.dumps(value)); return item
def list_request(models, p):
    r = models.ListTargetsRequest(); r.EventBusId, r.RuleId, r.Offset, r.Limit = p["event_bus_id"], p["rule_id"], 0, 100; return r
def create_request(models, p):
    r = models.CreateTargetRequest(); r.EventBusId, r.RuleId, r.Type = p["event_bus_id"], p["rule_id"], p["target_type"]; r.TargetDescription = _model(models.TargetDescription, p["target_description"]); r.EnableBatchDelivery, r.BatchTimeout, r.BatchEventCount = p.get("enable_batch_delivery"), p.get("batch_timeout"), p.get("batch_event_count"); return r
def update_request(models, p, target_id):
    r = models.UpdateTargetRequest(); r.EventBusId, r.RuleId, r.TargetId = p["event_bus_id"], p["rule_id"], target_id; r.EnableBatchDelivery, r.BatchTimeout, r.BatchEventCount = p.get("enable_batch_delivery"), p.get("batch_timeout"), p.get("batch_event_count"); return r
def delete_request(models, p, target_id):
    r = models.DeleteTargetRequest(); r.EventBusId, r.RuleId, r.TargetId = p["event_bus_id"], p["rule_id"], target_id; return r
def find(module, client, models, p):
    response = module.sdk_call(client.ListTargets, list_request(models, p)); items = [x._serialize(allow_none=True) for x in response.Targets or []]
    if p.get("target_id"): items = [x for x in items if x.get("TargetId") == p["target_id"]]
    elif p.get("target_type") and p.get("target_description") is not None: items = [x for x in items if x.get("Type") == p["target_type"] and x.get("TargetDescription") == p["target_description"]]
    else: return None
    if len(items) > 1: module.fail_json(msg="Multiple EventBridge targets matched; specify target_id")
    return items[0] if items else None


def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "event_bus_id": {"required": True}, "rule_id": {"required": True}, "target_id": {}, "target_type": {}, "target_description": {"type": "dict"}, "enable_batch_delivery": {"type": "bool"}, "batch_timeout": {"type": "int"}, "batch_event_count": {"type": "int"}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("target_id", "target_type")], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.EbClient, "eb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, target=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteTarget, delete_request(models, p, current["TargetId"]))
            module.exit_json(changed=True, **(diff or {}), target=None)
        if not current:
            missing = [k for k in ("target_type", "target_description") if p.get(k) is None]
            if missing: module.fail_json(msg="creation parameters are required for a new EventBridge target", missing=missing)
            target = {"Type": p["target_type"], "TargetDescription": p["target_description"], "EnableBatchDelivery": p.get("enable_batch_delivery"), "BatchTimeout": p.get("batch_timeout"), "BatchEventCount": p.get("batch_event_count")}; diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["target_id"] = module.sdk_call(client.CreateTarget, create_request(models, p)).TargetId; current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), target=current if not module.check_mode else target)
        before = {"Type": current.get("Type"), "TargetDescription": current.get("TargetDescription"), "EnableBatchDelivery": current.get("EnableBatchDelivery"), "BatchTimeout": current.get("BatchTimeout"), "BatchEventCount": current.get("BatchEventCount")}; target = {"Type": p.get("target_type") or before["Type"], "TargetDescription": p.get("target_description") if p.get("target_description") is not None else before["TargetDescription"], "EnableBatchDelivery": p.get("enable_batch_delivery") if p.get("enable_batch_delivery") is not None else before["EnableBatchDelivery"], "BatchTimeout": p.get("batch_timeout") if p.get("batch_timeout") is not None else before["BatchTimeout"], "BatchEventCount": p.get("batch_event_count") if p.get("batch_event_count") is not None else before["BatchEventCount"]}
        require_immutable_unchanged(module, before, target, ("Type", "TargetDescription"), "EventBridge target")
        if before == target: module.exit_json(changed=False, target=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode: module.sdk_call(client.UpdateTarget, update_request(models, p, current["TargetId"])); p["target_id"] = current["TargetId"]; current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), target=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__ == "__main__": main()
