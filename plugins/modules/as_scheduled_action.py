#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: as_scheduled_action
short_description: Manage Tencent Cloud Auto Scaling scheduled actions
version_added: "0.14.0"
description: Creates, updates and deletes scheduled capacity changes.
options:
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  scaling_group_id: {type: str, required: true, description: Auto Scaling group ID.}
  action_id: {type: str, description: Existing scheduled action ID.}
  name: {type: str, description: Scheduled action name.}
  min_size: {type: int, description: Minimum capacity. Required when state is present.}
  desired_capacity: {type: int, description: Desired capacity. Required when state is present.}
  max_size: {type: int, description: Maximum capacity. Required when state is present.}
  start_time: {type: str, description: First execution time in ISO 8601 format. Required when state is present.}
  end_time: {type: str, description: Recurrence end time in ISO 8601 format.}
  recurrence: {type: str, description: Cron recurrence expression.}
  disable_update_desired_capacity: {type: bool, default: false, description: Preserve current desired capacity.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.as_scheduled_action:
    scaling_group_id: asg-xxxxxxxx
    name: weekday-scale-out
    min_size: 2
    desired_capacity: 4
    max_size: 8
    start_time: '2026-09-01T01:00:00+08:00'
    recurrence: '0 0 9 * * MON-FRI'
"""
RETURN = r"""scheduled_action: {description: Scheduled action metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.autoscaling.v20180419 import autoscaling_client, models

    return models, autoscaling_client


def find(module, client, models, p):
    request = models.DescribeScheduledActionsRequest()
    request.Offset, request.Limit = 0, 100
    if p["action_id"]:
        request.ScheduledActionIds = [p["action_id"]]
    else:
        item = models.Filter()
        item.Name, item.Values = "auto-scaling-group-id", [p["scaling_group_id"]]
        request.Filters = [item]
    items = module.sdk_call(client.DescribeScheduledActions, request).ScheduledActionSet or []
    matches = [x._serialize(allow_none=True) for x in items if p["action_id"] or x.ScheduledActionName == p["name"]]
    if len(matches) > 1:
        module.fail_json(msg="Multiple scheduled actions have the requested name", name=p["name"])
    return matches[0] if matches else None


def wanted(p):
    return {
        "ScheduledActionName": p["name"],
        "MinSize": p["min_size"],
        "DesiredCapacity": p["desired_capacity"],
        "MaxSize": p["max_size"],
        "StartTime": p["start_time"],
        "EndTime": p["end_time"],
        "Recurrence": p["recurrence"],
        "DisableUpdateDesiredCapacity": p["disable_update_desired_capacity"],
    }


def apply(request, p, action_id=None):
    if action_id:
        request.ScheduledActionId = action_id
    else:
        request.AutoScalingGroupId = p["scaling_group_id"]
    request.ScheduledActionName, request.MinSize = p["name"], p["min_size"]
    request.DesiredCapacity, request.MaxSize, request.StartTime = p["desired_capacity"], p["max_size"], p["start_time"]
    request.EndTime, request.Recurrence = p["end_time"], p["recurrence"]
    request.DisableUpdateDesiredCapacity = p["disable_update_desired_capacity"]
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "scaling_group_id": {"required": True},
            "action_id": {},
            "name": {},
            "min_size": {"type": "int"},
            "desired_capacity": {"type": "int"},
            "max_size": {"type": "int"},
            "start_time": {},
            "end_time": {},
            "recurrence": {},
            "disable_update_desired_capacity": {"type": "bool", "default": False},
        },
        required_one_of=[("action_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and (not p["name"] or any(p[key] is None for key in ("min_size", "desired_capacity", "max_size", "start_time"))):
        module.fail_json(msg="name, min_size, desired_capacity, max_size and start_time are required when state=present")
    if p["state"] == "present" and not p["min_size"] <= p["desired_capacity"] <= p["max_size"]:
        module.fail_json(msg="capacity must satisfy min_size <= desired_capacity <= max_size")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.AutoscalingClient, "as.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, scheduled_action=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteScheduledActionRequest()
                request.ScheduledActionId = current["ScheduledActionId"]
                module.sdk_call(client.DeleteScheduledAction, request)
            module.exit_json(changed=True, **(diff or {}), scheduled_action=current if module.check_mode else None)
        target = wanted(p)
        before = {k: current.get(k) for k in target} if current else None
        if before == target:
            module.exit_json(changed=False, scheduled_action=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyScheduledAction, apply(models.ModifyScheduledActionRequest(), p, current["ScheduledActionId"]))
                p["action_id"] = current["ScheduledActionId"]
            else:
                p["action_id"] = module.sdk_call(client.CreateScheduledAction, apply(models.CreateScheduledActionRequest(), p)).ScheduledActionId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), scheduled_action=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
