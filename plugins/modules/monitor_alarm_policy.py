#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: monitor_alarm_policy
short_description: Manage a Tencent Cloud Monitor alarm policy
version_added: "0.13.0"
description: Creates, updates, enables, disables and deletes a Cloud Monitor alarm policy.
options:
  state: {description: Desired lifecycle state., type: str, choices: [present, absent], default: present}
  policy_id: {description: Existing alarm policy ID., type: str}
  name: {description: Alarm policy name., type: str}
  module: {description: API module selector., type: str, default: monitor}
  monitor_type: {description: Monitor data source type., type: str, default: MT_QCE}
  namespace: {description: Product namespace such as C(QCE/CVM)., type: str}
  remark: {description: Alarm policy remark., type: str, default: ''}
  enabled: {description: Whether evaluation is enabled., type: bool, default: true}
  condition: {description: Alarm metric condition in Tencent Cloud API shape., type: raw}
  event_condition: {description: Event alarm condition in Tencent Cloud API shape., type: raw}
  notice_ids: {description: Alarm notification rule IDs., type: list, elements: str, default: []}
  retries: {description: Number of retries for transient SDK failures., type: int, default: 5}
  waiter_delay: {description: Seconds between state-polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent value appended to SDK requests., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.monitor_alarm_policy:
    name: cvm-cpu-high
    namespace: QCE/CVM
    condition:
      IsUnionRule: 0
      Rules: []
'''
RETURN = r'''
policy: {description: Alarm policy metadata, type: dict, returned: always}
'''

import json

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_monitor():
    from tencentcloud.monitor.v20180724 import models, monitor_client

    return models, monitor_client


def _dict(value):
    return json.loads(value.to_json_string()) if value else None


def find_policy(module, client, models, policy_id, name, module_name):
    request = models.DescribeAlarmPoliciesRequest()
    request.Module, request.PageNumber, request.PageSize = module_name, 1, 100
    if name:
        request.PolicyName = name
    response = module.sdk_call(client.DescribeAlarmPolicies, request)
    for item in getattr(response, "PolicyList", None) or []:
        value = _dict(item)
        if (policy_id and value.get("PolicyId") == policy_id) or (not policy_id and value.get("PolicyName") == name):
            return value
    return None


def _model(models, cls_name, value):
    if value is None:
        return None
    obj = getattr(models, cls_name)()
    obj.from_json_string(json.dumps(value) if not isinstance(value, str) else value)
    return obj


def build_create_request(models, params):
    request = models.CreateAlarmPolicyRequest()
    request.Module, request.PolicyName = params["module"], params["name"]
    request.MonitorType, request.Namespace, request.Remark, request.Enable = (
        params["monitor_type"],
        params["namespace"],
        params["remark"],
        1 if params["enabled"] else 0,
    )
    request.Condition = _model(models, "AlarmPolicyCondition", params["condition"])
    request.EventCondition = _model(models, "AlarmPolicyEventCondition", params["event_condition"])
    request.NoticeIds = params["notice_ids"]
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "policy_id": {"type": "str"},
            "name": {"type": "str"},
            "module": {"type": "str", "default": "monitor"},
            "monitor_type": {"type": "str", "default": "MT_QCE"},
            "namespace": {"type": "str"},
            "remark": {"type": "str", "default": ""},
            "enabled": {"type": "bool", "default": True},
            "condition": {"type": "raw"},
            "event_condition": {"type": "raw"},
            "notice_ids": {"type": "list", "elements": "str", "default": []},
        },
        supports_check_mode=True,
    )
    p = module.params
    if not p["policy_id"] and not p["name"]:
        module.fail_json(msg="policy_id or name is required")
    if p["state"] == "present" and not p["policy_id"] and not p["namespace"]:
        module.fail_json(msg="namespace is required to create an alarm policy")
    module.require_sdk()
    models, monitor_client = _load_monitor()
    client = module.create_client(monitor_client.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        current = find_policy(module, client, models, p["policy_id"], p["name"], p["module"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, policy=None, msg="Alarm policy already absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), policy=current, msg="Would delete alarm policy")
            request = models.DeleteAlarmPolicyRequest()
            request.Module, request.PolicyIds = p["module"], [current["PolicyId"]]
            module.sdk_call(client.DeleteAlarmPolicy, request)
            module.exit_json(changed=True, **(diff or {}), policy=None, msg="Alarm policy deleted")
        desired = {"PolicyName": p["name"], "Remark": p["remark"], "Enable": 1 if p["enabled"] else 0}
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), policy=None, msg="Would create alarm policy")
            response = module.sdk_call(client.CreateAlarmPolicy, build_create_request(models, p))
            new_id = getattr(response, "PolicyId", None)
            module.exit_json(
                changed=True, **(diff or {}), policy=find_policy(module, client, models, new_id, p["name"], p["module"]), msg="Alarm policy created"
            )
        changes = []
        if p["name"] and current.get("PolicyName") != p["name"]:
            changes.append(("NAME", p["name"]))
        if (current.get("Remark") or "") != p["remark"]:
            changes.append(("REMARK", p["remark"]))
        current_enabled = bool(current.get("Enable"))
        status_drift = current_enabled != p["enabled"]
        if not changes and not status_drift:
            module.exit_json(changed=False, policy=current, msg="Alarm policy is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), policy=current, msg="Would update alarm policy")
        for key, value in changes:
            request = models.ModifyAlarmPolicyInfoRequest()
            request.Module, request.PolicyId, request.Key, request.Value = p["module"], current["PolicyId"], key, value
            module.sdk_call(client.ModifyAlarmPolicyInfo, request)
        if status_drift:
            request = models.ModifyAlarmPolicyStatusRequest()
            request.Module, request.PolicyId, request.Enable = p["module"], current["PolicyId"], 1 if p["enabled"] else 0
            module.sdk_call(client.ModifyAlarmPolicyStatus, request)
        module.exit_json(
            changed=True, **(diff or {}), policy=find_policy(module, client, models, current["PolicyId"], None, p["module"]), msg="Alarm policy updated"
        )
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
