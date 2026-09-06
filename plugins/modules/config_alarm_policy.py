#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: config_alarm_policy
short_description: Manage Tencent Cloud Config alarm policies
version_added: "0.14.0"
description: Creates, updates, enables, disables and deletes non-compliance notification policies.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired policy state.}
  alarm_policy_id: {type: int, description: Existing alarm policy ID; preferred for updates and deletion.}
  name: {type: str, description: "Policy name, also used for lookup."}
  event_type: {type: int, choices: [1], default: 1, description: Resource non-compliance event type.}
  event_scopes: {type: list, elements: int, choices: [1, 2], default: [1], description: Exact account scopes; one is current account and two is multi-account.}
  risk_levels: {type: list, elements: int, choices: [1, 2, 3], default: [1, 2, 3], description: Exact risk levels to notify.}
  notice_time: {type: str, description: Notification time window; required when state is present.}
  notification_mechanism: {type: str, description: Notification mechanism; required when state is present.}
  enabled: {type: bool, default: true, description: Whether the policy is active.}
  notice_period:
    type: list
    elements: int
    choices: [1, 2, 3, 4, 5, 6, 7]
    default: [1, 2, 3, 4, 5, 6, 7]
    description: Exact weekdays on which notifications are sent.
  description: {type: str, default: '', description: Policy description.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Notify on high-risk non-compliance every weekday
  susunola.tencentcloud.config_alarm_policy:
    region: ap-guangzhou
    name: high-risk-compliance
    risk_levels: [1]
    notice_period: [1, 2, 3, 4, 5]
    notice_time: 09:00-18:00
    notification_mechanism: USER
"""

RETURN = r"""alarm_policy: {description: Config alarm policy metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.config.v20220802 import models, config_client

    return models, config_client


def list_request(models, offset=0):
    request = models.ListAlarmPolicyRequest()
    request.Offset, request.Limit = offset, 100
    return request


def _apply(request, p):
    request.Name = p["name"]
    if hasattr(type(request), "Type"):
        request.Type = p["event_type"]
    request.EventScope, request.RiskLevel = sorted(set(p["event_scopes"])), sorted(set(p["risk_levels"]))
    request.NoticeTime, request.NotificationMechanism = p["notice_time"], p["notification_mechanism"]
    request.Status, request.NoticePeriod, request.Description = 1 if p["enabled"] else 2, sorted(set(p["notice_period"])), p["description"]
    return request


def create_request(models, p):
    return _apply(models.AddAlarmPolicyRequest(), p)


def update_request(models, p, policy_id):
    request = _apply(models.UpdateAlarmPolicyRequest(), p)
    request.AlarmPolicyId = policy_id
    return request


def delete_request(models, policy_id):
    request = models.DeleteAlarmPolicyRequest()
    request.AlarmPolicyId = policy_id
    return request


def find_policy(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.ListAlarmPolicy, list_request(models, offset))
        values = list(response.AlarmPolicyList or [])
        for value in values:
            item = value._serialize(allow_none=True)
            if p.get("alarm_policy_id") is not None and item.get("AlarmPolicyId") == p["alarm_policy_id"]:
                matches.append(item)
            elif p.get("alarm_policy_id") is None and p.get("name") and item.get("Name") == p["name"]:
                matches.append(item)
        offset += len(values)
        if offset >= int(response.Total or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple Config alarm policies matched; specify alarm_policy_id")
    return matches[0] if matches else None


def desired(p):
    return {
        "Name": p["name"],
        "Type": p["event_type"],
        "EventScope": sorted(set(p["event_scopes"])),
        "RiskLevel": sorted(set(p["risk_levels"])),
        "NoticeTime": p["notice_time"],
        "NotificationMechanism": p["notification_mechanism"],
        "Status": 1 if p["enabled"] else 2,
        "NoticePeriod": sorted(set(p["notice_period"])),
        "Description": p["description"],
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "alarm_policy_id": {"type": "int"},
            "name": {},
            "event_type": {"type": "int", "choices": [1], "default": 1},
            "event_scopes": {"type": "list", "elements": "int", "choices": [1, 2], "default": [1]},
            "risk_levels": {"type": "list", "elements": "int", "choices": [1, 2, 3], "default": [1, 2, 3]},
            "notice_time": {},
            "notification_mechanism": {},
            "enabled": {"type": "bool", "default": True},
            "notice_period": {"type": "list", "elements": "int", "choices": [1, 2, 3, 4, 5, 6, 7], "default": [1, 2, 3, 4, 5, 6, 7]},
            "description": {"default": ""},
        },
        required_one_of=[("alarm_policy_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and any(not p.get(key) for key in ("name", "notice_time", "notification_mechanism")):
        module.fail_json(msg="name, notice_time and notification_mechanism are required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ConfigClient, "config.tencentcloudapi.com")
    try:
        current = find_policy(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, alarm_policy=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteAlarmPolicy, delete_request(models, current["AlarmPolicyId"]))
            module.exit_json(changed=True, **(diff or {}), alarm_policy=current if module.check_mode else None)
        target = desired(p)
        before = {key: current.get(key) for key in target} if current else None
        if before:
            before["EventScope"], before["RiskLevel"], before["NoticePeriod"] = (
                sorted(set(before["EventScope"] or [])),
                sorted(set(before["RiskLevel"] or [])),
                sorted(set(before["NoticePeriod"] or [])),
            )
            before["Description"] = before["Description"] or ""
        if before == target:
            module.exit_json(changed=False, alarm_policy=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.UpdateAlarmPolicy, update_request(models, p, current["AlarmPolicyId"]))
            else:
                p["alarm_policy_id"] = module.sdk_call(client.AddAlarmPolicy, create_request(models, p)).AlarmPolicyId
            current = find_policy(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), alarm_policy=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
