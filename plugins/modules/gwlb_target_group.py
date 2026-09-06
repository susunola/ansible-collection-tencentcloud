#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: gwlb_target_group
short_description: Manage Tencent Cloud GWLB target groups
version_added: "0.14.0"
description: Creates, updates and deletes Gateway Load Balancer target groups.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  target_group_id: {type: str, description: Existing target group ID.}
  name: {type: str, description: Target group name.}
  vpc_id: {type: str, description: VPC ID required for creation and immutable afterwards.}
  port: {type: int, default: 6081, description: GENEVE backend port and immutable after creation.}
  protocol: {type: str, choices: [GENEVE], default: GENEVE, description: Backend protocol and immutable after creation.}
  schedule_algorithm: {type: str, choices: [WRR, LEAST_CONN, IP_HASH], description: Creation-time scheduling algorithm and immutable afterwards.}
  health_check: {type: dict, description: SDK TargetGroupHealthCheck payload.}
  all_dead_to_alive: {type: bool, default: false, description: Route traffic when all backends are unhealthy.}
  forwarding_mode: {type: str, description: Creation-time forwarding mode.}
  tags: {type: dict, description: Creation-time tags.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.gwlb_target_group:
    name: security-appliances
    vpc_id: vpc-xxxxxxxx
    health_check: {HealthSwitch: true, Protocol: TCP, Port: 80}
"""
RETURN = r"""target_group: {description: Effective GWLB target group metadata., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.gwlb.v20240906 import models, gwlb_client

    return models, gwlb_client


def _model(cls, value):
    if value is None:
        return None
    x = cls()
    x.from_json_string(json.dumps(value))
    return x


def describe_request(models, p):
    r = models.DescribeTargetGroupsRequest()
    r.Offset, r.Limit = 0, 100
    if p.get("target_group_id"):
        r.TargetGroupIds = [p["target_group_id"]]
    return r


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        x = models.TagInfo()
        x.TagKey, x.TagValue = key, value
        result.append(x)
    return result


def create_request(models, p):
    r = models.CreateTargetGroupRequest()
    r.TargetGroupName, r.VpcId, r.Port, r.Protocol = p["name"], p["vpc_id"], p["port"], p["protocol"]
    r.ScheduleAlgorithm, r.HealthCheck, r.AllDeadToAlive = (
        p.get("schedule_algorithm") or "WRR",
        _model(models.TargetGroupHealthCheck, p.get("health_check")),
        p["all_dead_to_alive"],
    )
    r.ForwardingMode, r.Tags = p.get("forwarding_mode"), _tags(models, p.get("tags"))
    return r


def update_request(models, p, target_group_id):
    r = models.ModifyTargetGroupAttributeRequest()
    r.TargetGroupId, r.TargetGroupName = target_group_id, p["name"]
    r.HealthCheck, r.AllDeadToAlive = _model(models.TargetGroupHealthCheck, p.get("health_check")), p["all_dead_to_alive"]
    return r


def delete_request(models, target_group_id):
    r = models.DeleteTargetGroupsRequest()
    r.TargetGroupIds = [target_group_id]
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeTargetGroups, describe_request(models, p))
    matches = []
    for item in response.TargetGroupSet or []:
        value = item._serialize(allow_none=True)
        if (p.get("target_group_id") and value.get("TargetGroupId") == p["target_group_id"]) or (
            not p.get("target_group_id") and value.get("TargetGroupName") == p.get("name")
        ):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple GWLB target groups matched; specify target_group_id")
    return matches[0] if matches else None


def comparable(v):
    return {
        "TargetGroupName": v.get("TargetGroupName"),
        "VpcId": v.get("VpcId"),
        "Port": v.get("Port"),
        "Protocol": v.get("Protocol"),
        "ScheduleAlgorithm": v.get("ScheduleAlgorithm"),
        "ForwardingMode": v.get("ForwardingMode"),
        "HealthCheck": v.get("HealthCheck"),
        "AllDeadToAlive": bool(v.get("AllDeadToAlive")),
    }


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "target_group_id": {},
        "name": {},
        "vpc_id": {},
        "port": {"type": "int", "default": 6081},
        "protocol": {"choices": ["GENEVE"], "default": "GENEVE"},
        "schedule_algorithm": {"choices": ["WRR", "LEAST_CONN", "IP_HASH"]},
        "health_check": {"type": "dict"},
        "all_dead_to_alive": {"type": "bool", "default": False},
        "forwarding_mode": {},
        "tags": {"type": "dict"},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("target_group_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.GwlbClient, "gwlb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, target_group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteTargetGroups, delete_request(models, current["TargetGroupId"]))
            module.exit_json(changed=True, **(diff or {}), target_group=None)
        if not current:
            missing = [k for k in ("name", "vpc_id") if not p.get(k)]
            if missing:
                module.fail_json(msg="creation parameters are required for a new GWLB target group", missing=missing)
            target = {
                "TargetGroupName": p["name"],
                "VpcId": p["vpc_id"],
                "Port": p["port"],
                "Protocol": p["protocol"],
                "ScheduleAlgorithm": p.get("schedule_algorithm") or "WRR",
                "ForwardingMode": p.get("forwarding_mode"),
                "HealthCheck": p.get("health_check"),
                "AllDeadToAlive": p["all_dead_to_alive"],
            }
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["target_group_id"] = module.sdk_call(client.CreateTargetGroup, create_request(models, p)).TargetGroupId
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), target_group=current if not module.check_mode else target)
        before = comparable(current)
        target = {
            "TargetGroupName": p.get("name") or before["TargetGroupName"],
            "VpcId": p.get("vpc_id") or before["VpcId"],
            "Port": p.get("port") or before["Port"],
            "Protocol": p.get("protocol") or before["Protocol"],
            "ScheduleAlgorithm": p.get("schedule_algorithm") or before["ScheduleAlgorithm"],
            "ForwardingMode": p.get("forwarding_mode") if p.get("forwarding_mode") is not None else before["ForwardingMode"],
            "HealthCheck": p.get("health_check") if p.get("health_check") is not None else before["HealthCheck"],
            "AllDeadToAlive": p["all_dead_to_alive"],
        }
        require_immutable_unchanged(module, before, target, ("VpcId", "Port", "Protocol", "ScheduleAlgorithm", "ForwardingMode"), "GWLB target group")
        if before == target:
            module.exit_json(changed=False, target_group=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            effective = dict(p)
            effective.update({"name": target["TargetGroupName"], "health_check": target["HealthCheck"], "all_dead_to_alive": target["AllDeadToAlive"]})
            module.sdk_call(client.ModifyTargetGroupAttribute, update_request(models, effective, current["TargetGroupId"]))
            p["target_group_id"] = current["TargetGroupId"]
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), target_group=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
