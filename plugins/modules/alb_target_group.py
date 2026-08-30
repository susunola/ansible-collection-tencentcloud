#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: alb_target_group
short_description: Manage Tencent Cloud ALB target groups
version_added: "0.14.0"
description: Creates, updates and deletes Application Load Balancer target groups.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  target_group_id: {type: str, description: Existing target group ID.}
  name: {type: str, description: Target group name.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  target_type: {type: str, choices: [Instance], default: Instance, description: Backend target type; immutable after creation.}
  protocol: {type: str, choices: [HTTP, HTTPS, GRPC, GRPCS], default: HTTP, description: Backend protocol; immutable after creation.}
  scheduler_algorithm: {type: str, choices: [wrr, wlc], default: wrr, description: Load-balancing algorithm.}
  keepalive_enabled: {type: bool, default: false, description: Enable backend keepalive.}
  health_check: {type: dict, description: SDK HealthCheckConfig payload.}
  sticky_session: {type: dict, description: SDK StickySessionConfig payload.}
  tags: {type: dict, description: Creation-time tags.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.alb_target_group:
    name: application-http
    vpc_id: vpc-xxxxxxxx
    protocol: HTTP
    health_check: {HealthCheckEnabled: true, HealthCheckPath: /health}
'''
RETURN = r'''target_group: {description: Effective ALB target group metadata., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.alb.v20251030 import models, alb_client
    return models, alb_client
def _model(cls, value):
    if value is None: return None
    item = cls(); item.from_json_string(json.dumps(value)); return item
def describe_request(models, p):
    r = models.DescribeTargetGroupsRequest(); r.MaxResults = 100
    if p.get("target_group_id"): r.TargetGroupIds = [p["target_group_id"]]
    return r
def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()): x = models.TagInfo(); x.TagKey, x.TagValue = key, value; result.append(x)
    return result
def create_request(models, p):
    r = models.CreateTargetGroupRequest(); r.TargetType, r.VpcId, r.Protocol, r.TargetGroupName = p["target_type"], p["vpc_id"], p["protocol"], p["name"]; r.SchedulerAlgorithm, r.KeepaliveEnabled = p["scheduler_algorithm"], p["keepalive_enabled"]; r.HealthCheckConfig, r.StickySessionConfig, r.Tags = _model(models.HealthCheckConfig, p.get("health_check")), _model(models.StickySessionConfig, p.get("sticky_session")), _tags(models, p.get("tags")); return r
def update_request(models, p, target_group_id):
    r = models.ModifyTargetGroupAttributesRequest(); r.TargetGroupId, r.TargetGroupName = target_group_id, p["name"]; r.SchedulerAlgorithm, r.KeepaliveEnabled = p["scheduler_algorithm"], p["keepalive_enabled"]; r.HealthCheckConfig, r.StickySessionConfig = _model(models.HealthCheckConfig, p.get("health_check")), _model(models.StickySessionConfig, p.get("sticky_session")); return r
def delete_request(models, target_group_id):
    r = models.DeleteTargetGroupsRequest(); r.TargetGroupIds = [target_group_id]; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeTargetGroups, describe_request(models, p)); matches = []
    for item in response.TargetGroups or []:
        value = item._serialize(allow_none=True)
        if (p.get("target_group_id") and value.get("TargetGroupId") == p["target_group_id"]) or (not p.get("target_group_id") and value.get("TargetGroupName") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple ALB target groups matched; specify target_group_id")
    return matches[0] if matches else None
def comparable(v): return {"TargetGroupName": v.get("TargetGroupName"), "VpcId": v.get("VpcId"), "TargetType": v.get("TargetType"), "Protocol": v.get("Protocol"), "SchedulerAlgorithm": v.get("SchedulerAlgorithm"), "KeepaliveEnabled": bool(v.get("KeepaliveEnabled")), "HealthCheckConfig": v.get("HealthCheckConfig"), "StickySessionConfig": v.get("StickySessionConfig")}
def desired(p, current=None):
    old = comparable(current) if current else {}; return {"TargetGroupName": p.get("name") or old.get("TargetGroupName"), "VpcId": p.get("vpc_id") or old.get("VpcId"), "TargetType": p.get("target_type") or old.get("TargetType"), "Protocol": p.get("protocol") or old.get("Protocol"), "SchedulerAlgorithm": p["scheduler_algorithm"], "KeepaliveEnabled": p["keepalive_enabled"], "HealthCheckConfig": p.get("health_check") if p.get("health_check") is not None else old.get("HealthCheckConfig"), "StickySessionConfig": p.get("sticky_session") if p.get("sticky_session") is not None else old.get("StickySessionConfig")}
def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "target_group_id": {}, "name": {}, "vpc_id": {}, "target_type": {"choices": ["Instance"], "default": "Instance"}, "protocol": {"choices": ["HTTP", "HTTPS", "GRPC", "GRPCS"], "default": "HTTP"}, "scheduler_algorithm": {"choices": ["wrr", "wlc"], "default": "wrr"}, "keepalive_enabled": {"type": "bool", "default": False}, "health_check": {"type": "dict"}, "sticky_session": {"type": "dict"}, "tags": {"type": "dict"}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("target_group_id", "name")], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.AlbClient, "alb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, target_group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteTargetGroups, delete_request(models, current["TargetGroupId"]))
            module.exit_json(changed=True, **(diff or {}), target_group=None)
        if not current:
            missing = [k for k in ("name", "vpc_id") if not p.get(k)]
            if missing: module.fail_json(msg="creation parameters are required for a new ALB target group", missing=missing)
        before, target = comparable(current) if current else None, desired(p, current)
        if before == target: module.exit_json(changed=False, target_group=current)
        if current: require_immutable_unchanged(module, before, target, ("VpcId", "TargetType", "Protocol"), "ALB target group")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            effective = dict(p); effective.update({"name": target["TargetGroupName"], "scheduler_algorithm": target["SchedulerAlgorithm"], "keepalive_enabled": target["KeepaliveEnabled"], "health_check": target["HealthCheckConfig"], "sticky_session": target["StickySessionConfig"]})
            response = module.sdk_call(client.ModifyTargetGroupAttributes if current else client.CreateTargetGroup, update_request(models, effective, current["TargetGroupId"]) if current else create_request(models, effective)); p["target_group_id"] = current["TargetGroupId"] if current else response.TargetGroupId; current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), target_group=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__ == "__main__": main()
