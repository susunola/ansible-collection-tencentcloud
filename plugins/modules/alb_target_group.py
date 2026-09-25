#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: alb_target_group
short_description: Manage Tencent Cloud ALB target groups
version_added: "0.14.0"
description:
  - Creates, updates, and deletes Application Load Balancer target groups.
  - Reads all target-group pages before determining whether a group is absent
    or whether a name uniquely identifies one group.
options:
  state:
    description:
      - C(present) creates the target group with V(CreateTargetGroup) when it does not exist and updates it
        with V(ModifyTargetGroupAttributes) when it differs. C(absent) deletes it with V(DeleteTargetGroups).
      - The module waits for the change to be observable before returning, bounded by O(waiter_timeout).
    type: str
    choices: [present, absent]
    default: present
  target_group_id:
    description:
      - Existing target group ID.
    type: str
  name:
    description:
      - Identifies the target group to manage; one of this or O(target_group_id) is required.
    type: str
  vpc_id:
    description:
      - VPC ID; immutable after creation.
    type: str
  target_type:
    description:
      - Backend target type; defaults to Instance on creation and is immutable thereafter.
    type: str
    choices: [Instance]
  protocol:
    description:
      - Backend protocol; defaults to HTTP on creation and is immutable thereafter.
    type: str
    choices: [HTTP, HTTPS, GRPC, GRPCS]
  scheduler_algorithm:
    description:
      - Load-balancing algorithm.
    type: str
    choices: [wrr, wlc]
    default: wrr
  keepalive_enabled:
    description:
      - Enable backend keepalive.
    type: bool
    default: false
  health_check:
    description:
      - SDK HealthCheckConfig payload.
    type: dict
  sticky_session:
    description:
      - SDK StickySessionConfig payload.
    type: dict
  tags:
    description:
      - Creation-time tags.
    type: dict

attributes:
  check_mode:
    description: Predicts changes without sending API write requests.
    support: full
  diff_mode:
    description: Returns a comparison of the observed and requested target group settings.
    support: partial
    details: API-assigned and other unmanaged fields are not part of the diff.
  idempotent:
    description: Compares observable target-group settings before writing.
    support: partial
    details: Waits for observable target-group settings to converge after writes.

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
seealso:
  - module: susunola.tencentcloud.alb_target_group_info
    description: Gather information about Tencent Cloud ALB target groups.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.alb_target_group:
    name: application-http
    vpc_id: vpc-xxxxxxxx
    protocol: HTTP
    health_check: {HealthCheckEnabled: true, HealthCheckPath: /health}

- name: Delete the target group
  susunola.tencentcloud.alb_target_group:
    state: absent
    name: application-http
"""
RETURN = r"""target_group:
  description:
    - Effective ALB target group metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    TargetGroupId: lbtg-20001
    TargetGroupName: app-http
    VpcId: vpc-1
    TargetType: Instance
    Protocol: HTTP
    SchedulerAlgorithm: wrr
    KeepaliveEnabled: false
    HealthCheckConfig:
      HealthCheckEnabled: true
      HealthCheckPath: /health
    StickySessionConfig:
      StickySessionSwitch: 'OFF'
"""
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, fail_from_sdk_error


def _load():
    from tencentcloud.alb.v20251030 import models, alb_client

    return models, alb_client


def _model(cls, value):
    if value is None:
        return None
    item = cls()
    item.from_json_string(json.dumps(value))
    return item


def describe_request(models, p, next_token=None):
    r = models.DescribeTargetGroupsRequest()
    r.MaxResults = 100
    if p.get("target_group_id"):
        r.TargetGroupIds = [p["target_group_id"]]
    if next_token:
        r.NextToken = next_token
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
    r.TargetType, r.VpcId, r.Protocol, r.TargetGroupName = p.get("target_type") or "Instance", p["vpc_id"], p.get("protocol") or "HTTP", p["name"]
    r.SchedulerAlgorithm, r.KeepaliveEnabled = p["scheduler_algorithm"], p["keepalive_enabled"]
    r.HealthCheckConfig, r.StickySessionConfig, r.Tags = (
        _model(models.HealthCheckConfig, p.get("health_check")),
        _model(models.StickySessionConfig, p.get("sticky_session")),
        _tags(models, p.get("tags")),
    )
    return r


def update_request(models, p, target_group_id):
    r = models.ModifyTargetGroupAttributesRequest()
    r.TargetGroupId, r.TargetGroupName = target_group_id, p["name"]
    r.SchedulerAlgorithm, r.KeepaliveEnabled = p["scheduler_algorithm"], p["keepalive_enabled"]
    r.HealthCheckConfig, r.StickySessionConfig = _model(models.HealthCheckConfig, p.get("health_check")), _model(
        models.StickySessionConfig, p.get("sticky_session")
    )
    return r


def delete_request(models, target_group_id):
    r = models.DeleteTargetGroupsRequest()
    r.TargetGroupIds = [target_group_id]
    return r


def find(module, client, models, p):
    matches = []
    next_token = None
    seen_tokens = set()
    while True:
        response = module.sdk_call(client.DescribeTargetGroups, describe_request(models, p, next_token))
        if getattr(response, "TargetGroups", None) is None:
            module.fail_json(msg="ALB target group list is not observable")
        for item in response.TargetGroups:
            value = item._serialize(allow_none=True)
            if (p.get("target_group_id") and value.get("TargetGroupId") == p["target_group_id"]) or (
                not p.get("target_group_id") and value.get("TargetGroupName") == p.get("name")
            ):
                matches.append(value)
        next_token = getattr(response, "NextToken", None)
        if not next_token:
            break
        if next_token in seen_tokens:
            module.fail_json(msg="ALB target group pagination returned a repeated token")
        seen_tokens.add(next_token)
    if len(matches) > 1:
        module.fail_json(msg="Multiple ALB target groups matched; specify target_group_id")
    return matches[0] if matches else None


def comparable(v):
    return {
        "TargetGroupName": v.get("TargetGroupName"),
        "VpcId": v.get("VpcId"),
        "TargetType": v.get("TargetType"),
        "Protocol": v.get("Protocol"),
        "SchedulerAlgorithm": v.get("SchedulerAlgorithm"),
        "KeepaliveEnabled": bool(v.get("KeepaliveEnabled")),
        "HealthCheckConfig": v.get("HealthCheckConfig"),
        "StickySessionConfig": v.get("StickySessionConfig"),
    }


def desired(p, current=None):
    old = comparable(current) if current else {}
    return {
        "TargetGroupName": p.get("name") or old.get("TargetGroupName"),
        "VpcId": p.get("vpc_id") or old.get("VpcId"),
        "TargetType": p.get("target_type") or old.get("TargetType") or "Instance",
        "Protocol": p.get("protocol") or old.get("Protocol") or "HTTP",
        "SchedulerAlgorithm": p["scheduler_algorithm"],
        "KeepaliveEnabled": p["keepalive_enabled"],
        "HealthCheckConfig": p.get("health_check") if p.get("health_check") is not None else old.get("HealthCheckConfig"),
        "StickySessionConfig": p.get("sticky_session") if p.get("sticky_session") is not None else old.get("StickySessionConfig"),
    }


def wait_for_group(module, client, models, p, expected):
    deadline = time.monotonic() + max(0, p["waiter_timeout"])
    while True:
        observed = find(module, client, models, p)
        if (observed is None if expected is None else observed is not None and comparable(observed) == expected):
            return observed
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            module.fail_json(msg="ALB target group did not converge before timeout", target_group=observed, expected=expected)
        time.sleep(min(max(0, p["waiter_delay"]), remaining))


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "target_group_id": {},
        "name": {},
        "vpc_id": {},
        "target_type": {"choices": ["Instance"]},
        "protocol": {"choices": ["HTTP", "HTTPS", "GRPC", "GRPCS"]},
        "scheduler_algorithm": {"choices": ["wrr", "wlc"], "default": "wrr"},
        "keepalive_enabled": {"type": "bool", "default": False},
        "health_check": {"type": "dict"},
        "sticky_session": {"type": "dict"},
        "tags": {"type": "dict"},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("target_group_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.AlbClient, "alb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, target_group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteTargetGroups, delete_request(models, current["TargetGroupId"]))
                p["target_group_id"] = current["TargetGroupId"]
                wait_for_group(module, client, models, p, None)
            module.exit_json(changed=True, **(diff or {}), target_group=None)
        if not current:
            missing = [k for k in ("name", "vpc_id") if not p.get(k)]
            if missing:
                module.fail_json(msg="creation parameters are required for a new ALB target group", missing=missing)
        before, target = comparable(current) if current else None, desired(p, current)
        if before == target:
            module.exit_json(changed=False, target_group=current)
        if current:
            require_immutable_unchanged(module, before, target, ("VpcId", "TargetType", "Protocol"), "ALB target group")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            effective = dict(p)
            effective.update(
                {
                    "name": target["TargetGroupName"],
                    "scheduler_algorithm": target["SchedulerAlgorithm"],
                    "keepalive_enabled": target["KeepaliveEnabled"],
                    "health_check": target["HealthCheckConfig"],
                    "sticky_session": target["StickySessionConfig"],
                }
            )
            response = module.sdk_call(
                client.ModifyTargetGroupAttributes if current else client.CreateTargetGroup,
                update_request(models, effective, current["TargetGroupId"]) if current else create_request(models, effective),
            )
            p["target_group_id"] = current["TargetGroupId"] if current else response.TargetGroupId
            current = wait_for_group(module, client, models, p, target)
        module.exit_json(changed=True, **(diff or {}), target_group=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
