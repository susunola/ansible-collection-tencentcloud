#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cvm_instance_action_timer
short_description: Manage Tencent Cloud CVM instance action timers
version_added: "0.14.0"
description: Creates, replaces and deletes an unexecuted scheduled termination timer for one CVM instance.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: CVM instance ID.}
  action_time: {type: str, description: UTC ISO8601 execution time at least five minutes in the future.}
  timer_id: {type: str, description: Existing action-timer ID; useful when more than one timer exists.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cvm_instance_action_timer:
    instance_id: ins-xxxxxxxx
    action_time: '2026-09-01T12:00:00Z'
'''
RETURN = r'''action_timer: {description: Effective scheduled action., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cvm.v20170312 import models, cvm_client
    return models, cvm_client
def describe_request(models, p):
    request = models.DescribeInstancesActionTimerRequest(); request.InstanceIds, request.TimerAction, request.StatusList = [p["instance_id"]], "TerminateInstances", ["UNDO"]
    if p.get("timer_id"): request.ActionTimerIds = [p["timer_id"]]
    return request
def create_request(models, p):
    timer = models.ActionTimer(); timer.TimerAction, timer.ActionTime = "TerminateInstances", p["action_time"]
    request = models.ImportInstancesActionTimerRequest(); request.InstanceIds, request.ActionTimer = [p["instance_id"]], timer; return request
def delete_request(models, timer_id):
    request = models.DeleteInstancesActionTimerRequest(); request.ActionTimerIds = [timer_id]; return request
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeInstancesActionTimer, describe_request(models, p)); values = [item._serialize(allow_none=True) for item in (response.ActionTimers or [])]
    if len(values) > 1: module.fail_json(msg="Multiple unexecuted termination timers matched; specify timer_id", timer_ids=[v.get("ActionTimerId") for v in values])
    return values[0] if values else None
def comparable(v): return {"InstanceId": v.get("InstanceId"), "TimerAction": v.get("TimerAction"), "ActionTime": v.get("ActionTime"), "Status": v.get("Status")}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "action_time": {}, "timer_id": {}}, required_if=[("state", "present", ["action_time"])], supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CvmClient, "cvm.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, action_timer=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode: module.sdk_call(client.DeleteInstancesActionTimer, delete_request(models, current["ActionTimerId"]))
            module.exit_json(changed=True, **(diff or {}), action_timer=current if module.check_mode else None)
        target = {"InstanceId": p["instance_id"], "TimerAction": "TerminateInstances", "ActionTime": p["action_time"], "Status": "UNDO"}; before = comparable(current) if current else None
        if before == target: module.exit_json(changed=False, action_timer=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current: module.sdk_call(client.DeleteInstancesActionTimer, delete_request(models, current["ActionTimerId"]))
            ids = module.sdk_call(client.ImportInstancesActionTimer, create_request(models, p)).ActionTimerIds or []
            p["timer_id"] = ids[0] if ids else None; current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), action_timer=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
