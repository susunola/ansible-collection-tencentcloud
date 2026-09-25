#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: as_scaling_policy
short_description: Manage Tencent Cloud Auto Scaling policies
version_added: "0.14.0"
description: Creates, updates and deletes simple or target-tracking scaling policies.
options:

  state:
    description:
      - C(present) creates the scaling policy with V(CreateScalingPolicy) when it does not exist and updates
        it with V(ModifyScalingPolicy) when it differs. C(absent) deletes it with V(DeleteScalingPolicy).
    type: str
    choices: [present, absent]
    default: present
  scaling_group_id:
    description:
      - Auto Scaling group ID.
    type: str
    required: true
  policy_id:
    description:
      - Identifies the scaling policy to manage; one of this or O(name) is required.
    type: str
  name:
    description:
      - Identifies the scaling policy to manage; one of this or O(policy_id) is required.
    type: str
  policy_type:
    description:
      - How the policy adjusts capacity when it runs.
      - C(SIMPLE) applies one adjustment per run, sized by the policy's own
        parameters.
      - C(TARGET_TRACKING) keeps the chosen metric at a target value by
        adjusting capacity as the metric moves.
    type: str
    choices: [SIMPLE, TARGET_TRACKING]
    default: SIMPLE
  adjustment_type:
    description: Capacity adjustment type.
    type: str
    choices: [CHANGE_IN_CAPACITY, EXACT_CAPACITY, PERCENT_CHANGE_IN_CAPACITY]
    default: CHANGE_IN_CAPACITY
  adjustment_value:
    description:
      - Capacity adjustment value.
    type: int
    default: 1
  cooldown:
    description:
      - Cooldown seconds.
    type: int
    default: 300
  predefined_metric_type:
    description:
      - Target-tracking metric.
    type: str
  target_value:
    description:
      - Target metric value.
    type: int
  estimated_instance_warmup:
    description:
      - Instance warmup seconds.
    type: int
    default: 300
  disable_scale_in:
    description:
      - Disable target-tracking scale-in.
    type: bool
    default: false
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.as_scaling_policy_info
    description: Gather information about Tencent Cloud AUTOSCALING scaling policies.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.as_scaling_policy:
    scaling_group_id: asg-xxxxxxxx
    name: add-two
    adjustment_value: 2

- name: Delete the scaling policy
  susunola.tencentcloud.as_scaling_policy:
    state: absent
    name: add-two
    scaling_group_id: asg-xxxxxxxx
"""
RETURN = r"""scaling_policy:
  description:
    - Scaling policy metadata.
  returned: always
  type: dict"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, fail_from_sdk_error


def _load():
    from tencentcloud.autoscaling.v20180419 import autoscaling_client, models

    return models, autoscaling_client


def find(module, client, models, p):
    request = models.DescribeScalingPoliciesRequest()
    request.Limit, request.Offset = 100, 0
    if p["policy_id"]:
        request.AutoScalingPolicyIds = [p["policy_id"]]
    else:
        item = models.Filter()
        item.Name, item.Values = "auto-scaling-group-id", [p["scaling_group_id"]]
        request.Filters = [item]
    items = module.sdk_call(client.DescribeScalingPolicies, request).ScalingPolicySet or []
    matches = [x._serialize(allow_none=True) for x in items if p["policy_id"] or x.ScalingPolicyName == p["name"]]
    if len(matches) > 1:
        module.fail_json(msg="Multiple scaling policies have the requested name", name=p["name"])
    return matches[0] if matches else None


def wanted(p):
    result = {
        "ScalingPolicyName": p["name"],
        "ScalingPolicyType": p["policy_type"],
        "AdjustmentType": p["adjustment_type"],
        "AdjustmentValue": p["adjustment_value"],
        "Cooldown": p["cooldown"],
    }
    if p["policy_type"] == "TARGET_TRACKING":
        result.update(
            PredefinedMetricType=p["predefined_metric_type"],
            TargetValue=p["target_value"],
            EstimatedInstanceWarmup=p["estimated_instance_warmup"],
            DisableScaleIn=p["disable_scale_in"],
        )
    return result


def apply(request, p, policy_id=None):
    if policy_id:
        request.AutoScalingPolicyId = policy_id
    else:
        request.AutoScalingGroupId, request.ScalingPolicyType = p["scaling_group_id"], p["policy_type"]
    request.ScalingPolicyName, request.AdjustmentType = p["name"], p["adjustment_type"]
    request.AdjustmentValue, request.Cooldown = p["adjustment_value"], p["cooldown"]
    if p["policy_type"] == "TARGET_TRACKING":
        request.PredefinedMetricType, request.TargetValue = p["predefined_metric_type"], p["target_value"]
        request.EstimatedInstanceWarmup, request.DisableScaleIn = p["estimated_instance_warmup"], p["disable_scale_in"]
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "scaling_group_id": {"required": True},
            "policy_id": {},
            "name": {},
            "policy_type": {"choices": ["SIMPLE", "TARGET_TRACKING"], "default": "SIMPLE"},
            "adjustment_type": {"choices": ["CHANGE_IN_CAPACITY", "EXACT_CAPACITY", "PERCENT_CHANGE_IN_CAPACITY"], "default": "CHANGE_IN_CAPACITY"},
            "adjustment_value": {"type": "int", "default": 1},
            "cooldown": {"type": "int", "default": 300},
            "predefined_metric_type": {},
            "target_value": {"type": "int"},
            "estimated_instance_warmup": {"type": "int", "default": 300},
            "disable_scale_in": {"type": "bool", "default": False},
        },
        required_one_of=[("policy_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    if p["policy_type"] == "TARGET_TRACKING" and (not p["predefined_metric_type"] or p["target_value"] is None):
        module.fail_json(msg="predefined_metric_type and target_value are required for TARGET_TRACKING")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.AutoscalingClient, "as.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, scaling_policy=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteScalingPolicyRequest()
                request.AutoScalingPolicyId = current["AutoScalingPolicyId"]
                module.sdk_call(client.DeleteScalingPolicy, request)
            module.exit_json(changed=True, **(diff or {}), scaling_policy=current if module.check_mode else None)
        target = wanted(p)
        before = {k: current.get(k) for k in target} if current else None
        if before == target:
            module.exit_json(changed=False, scaling_policy=current)
        if current:
            require_immutable_unchanged(module, current, target, ("ScalingPolicyType",), "Auto Scaling policy")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyScalingPolicy, apply(models.ModifyScalingPolicyRequest(), p, current["AutoScalingPolicyId"]))
                p["policy_id"] = current["AutoScalingPolicyId"]
            else:
                p["policy_id"] = module.sdk_call(client.CreateScalingPolicy, apply(models.CreateScalingPolicyRequest(), p)).AutoScalingPolicyId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), scaling_policy=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
