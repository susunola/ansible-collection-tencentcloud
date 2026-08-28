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
  project_id: {description: Project ID assigned when creating the policy., type: int}
  filter: {description: Alarm-policy dimension filter in Tencent Cloud API shape., type: raw}
  group_by: {description: Dimension names used to aggregate alarm objects., type: list, elements: str}
  trigger_tasks: {description: Alarm trigger tasks in Tencent Cloud API shape., type: list, elements: raw}
  hierarchical_notices: {description: Hierarchical notification bindings in Tencent Cloud API shape., type: list, elements: raw}
  notice_content_template_bindings: {description: Notification content-template bindings in Tencent Cloud API shape., type: list, elements: raw}
  tags: {description: Alarm-policy tags applied at creation., type: dict}
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
import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_monitor():
    from tencentcloud.monitor.v20180724 import models, monitor_client

    return models, monitor_client


def _dict(value):
    return json.loads(value.to_json_string()) if value else None


def find_policy(module, client, models, policy_id, name, module_name):
    page, matches = 1, []
    while True:
        request = models.DescribeAlarmPoliciesRequest()
        request.Module, request.PageNumber, request.PageSize = module_name, page, 100
        if name:
            request.PolicyName = name
        response = module.sdk_call(client.DescribeAlarmPolicies, request)
        items = list(getattr(response, "PolicyList", None) or [])
        for item in items:
            value = _dict(item)
            if (policy_id and value.get("PolicyId") == policy_id) or (not policy_id and value.get("PolicyName") == name):
                matches.append(value)
        total = int(getattr(response, "TotalCount", 0) or 0)
        if not items or page * 100 >= total:
            break
        page += 1
    if len(matches) > 1:
        module.fail_json(msg="Multiple alarm policies have the requested name", name=name)
    return matches[0] if matches else None


def _model(models, cls_name, value):
    if value is None:
        return None
    obj = getattr(models, cls_name)()
    obj.from_json_string(json.dumps(value) if not isinstance(value, str) else value)
    return obj


def _model_list(models, cls_name, values):
    if values is None:
        return None
    return [_model(models, cls_name, value) for value in values]


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
    request.ProjectId = params.get("project_id")
    request.Filter = _model(models, "AlarmPolicyFilter", params.get("filter"))
    request.GroupBy = params.get("group_by")
    request.TriggerTasks = _model_list(models, "AlarmPolicyTriggerTask", params.get("trigger_tasks"))
    request.HierarchicalNotices = _model_list(models, "AlarmHierarchicalNotice", params.get("hierarchical_notices"))
    request.NoticeContentTmplBindInfos = _model_list(
        models, "NoticeContentTmplBindInfo", params.get("notice_content_template_bindings")
    )
    if params.get("tags") is not None:
        request.Tags = []
        for key, value in sorted(params["tags"].items()):
            tag = models.Tag()
            tag.Key, tag.Value = str(key), str(value)
            request.Tags.append(tag)
    return request


def build_condition_request(models, params, policy_id, current=None):
    current = current or {}
    request = models.ModifyAlarmPolicyConditionRequest()
    request.Module, request.PolicyId = params["module"], policy_id
    request.PolicyName = params["name"] or current.get("PolicyName")
    condition = params["condition"] if params["condition"] is not None else current.get("Condition")
    event_condition = params["event_condition"] if params["event_condition"] is not None else current.get("EventCondition")
    request.Condition = _model(models, "AlarmPolicyCondition", condition)
    request.EventCondition = _model(models, "AlarmPolicyEventCondition", event_condition)
    request.NoticeIds = params["notice_ids"]
    request.Filter = _model(
        models, "AlarmPolicyFilter",
        params.get("filter") if params.get("filter") is not None else current.get("Filter"),
    )
    request.GroupBy = params.get("group_by") if params.get("group_by") is not None else current.get("GroupBy")
    return request


def build_notice_request(models, params, policy_id):
    request = models.ModifyAlarmPolicyNoticeRequest()
    request.Module, request.PolicyId = params["module"], policy_id
    request.NoticeIds = params["notice_ids"]
    request.HierarchicalNotices = _model_list(models, "AlarmHierarchicalNotice", params.get("hierarchical_notices"))
    request.NoticeContentTmplBindInfos = _model_list(
        models, "NoticeContentTmplBindInfo", params.get("notice_content_template_bindings")
    )
    return request


def build_tasks_request(models, params, policy_id):
    request = models.ModifyAlarmPolicyTasksRequest()
    request.Module, request.PolicyId = params["module"], policy_id
    request.TriggerTasks = _model_list(models, "AlarmPolicyTriggerTask", params.get("trigger_tasks"))
    return request


def _contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _contains(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _contains(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def _policy_converged(current, desired):
    if not current:
        return False
    return all((
        not desired.get("PolicyName") or current.get("PolicyName") == desired["PolicyName"],
        (current.get("Remark") or "") == desired["Remark"],
        bool(current.get("Enable")) == bool(desired["Enable"]),
        desired.get("Condition") is None or _contains(current.get("Condition"), desired["Condition"]),
        desired.get("EventCondition") is None or _contains(current.get("EventCondition"), desired["EventCondition"]),
        desired.get("Filter") is None or _contains(current.get("Filter"), desired["Filter"]),
        desired.get("GroupBy") is None or current.get("GroupBy") == desired["GroupBy"],
        desired.get("TriggerTasks") is None or _contains(current.get("TriggerTasks"), desired["TriggerTasks"]),
        desired.get("HierarchicalNotices") is None or _contains(current.get("HierarchicalNotices"), desired["HierarchicalNotices"]),
        desired.get("NoticeContentTmplBindInfos") is None or _contains(current.get("NoticeContentTmplBindInfos"), desired["NoticeContentTmplBindInfos"]),
        sorted(current.get("NoticeIds") or []) == sorted(desired.get("NoticeIds") or []),
    ))


def wait_for_policy(module, client, models, policy_id, name, module_name, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_policy(module, client, models, policy_id, name, module_name)
        if absent and current is None:
            return None
        if not absent and _policy_converged(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(
                msg="Timed out waiting for alarm policy convergence",
                policy=current,
                expected="absent" if absent else desired,
            )
        time.sleep(module.params["waiter_delay"])


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
            "project_id": {"type": "int"},
            "filter": {"type": "raw"},
            "group_by": {"type": "list", "elements": "str"},
            "trigger_tasks": {"type": "list", "elements": "raw"},
            "hierarchical_notices": {"type": "list", "elements": "raw"},
            "notice_content_template_bindings": {"type": "list", "elements": "raw"},
            "tags": {"type": "dict"},
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
            wait_for_policy(
                module, client, models, current["PolicyId"], None, p["module"], absent=True,
            )
            module.exit_json(changed=True, **(diff or {}), policy=None, msg="Alarm policy deleted")
        desired = {
            "PolicyName": p["name"], "Remark": p["remark"],
            "Enable": 1 if p["enabled"] else 0,
            "Condition": p["condition"], "EventCondition": p["event_condition"],
            "NoticeIds": p["notice_ids"],
            "Filter": p["filter"], "GroupBy": p["group_by"],
            "TriggerTasks": p["trigger_tasks"],
            "HierarchicalNotices": p["hierarchical_notices"],
            "NoticeContentTmplBindInfos": p["notice_content_template_bindings"],
        }
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), policy=None, msg="Would create alarm policy")
            response = module.sdk_call(client.CreateAlarmPolicy, build_create_request(models, p))
            new_id = getattr(response, "PolicyId", None)
            current = wait_for_policy(
                module, client, models, new_id, p["name"], p["module"], desired,
            )
            module.exit_json(
                changed=True, **(diff or {}), policy=current, msg="Alarm policy created"
            )
        changes = []
        if p["name"] and current.get("PolicyName") != p["name"]:
            changes.append(("NAME", p["name"]))
        if (current.get("Remark") or "") != p["remark"]:
            changes.append(("REMARK", p["remark"]))
        current_enabled = bool(current.get("Enable"))
        status_drift = current_enabled != p["enabled"]
        condition_drift = any((
            p["condition"] is not None and not _contains(current.get("Condition"), p["condition"]),
            p["event_condition"] is not None and not _contains(current.get("EventCondition"), p["event_condition"]),
            p["filter"] is not None and not _contains(current.get("Filter"), p["filter"]),
            p["group_by"] is not None and current.get("GroupBy") != p["group_by"],
        ))
        notice_drift = any((
            sorted(current.get("NoticeIds") or []) != sorted(p["notice_ids"]),
            p["hierarchical_notices"] is not None and not _contains(current.get("HierarchicalNotices"), p["hierarchical_notices"]),
            p["notice_content_template_bindings"] is not None and not _contains(
                current.get("NoticeContentTmplBindInfos"), p["notice_content_template_bindings"]
            ),
        ))
        tasks_drift = p["trigger_tasks"] is not None and not _contains(current.get("TriggerTasks"), p["trigger_tasks"])
        immutable_drift = {}
        if p["project_id"] is not None and int(current.get("ProjectId") or 0) != p["project_id"]:
            immutable_drift["project_id"] = {"current": current.get("ProjectId"), "desired": p["project_id"]}
        if p["tags"] is not None:
            current_tags = {item.get("Key"): item.get("Value") for item in (current.get("Tags") or [])}
            if current_tags != {str(k): str(v) for k, v in p["tags"].items()}:
                immutable_drift["tags"] = {"current": current_tags, "desired": p["tags"]}
        if immutable_drift:
            module.fail_json(msg="Alarm policy has immutable attribute drift", immutable_drift=immutable_drift)
        if not changes and not status_drift and not condition_drift and not notice_drift and not tasks_drift:
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
        if condition_drift:
            module.sdk_call(
                client.ModifyAlarmPolicyCondition,
                build_condition_request(models, p, current["PolicyId"], current),
            )
        if notice_drift:
            module.sdk_call(
                client.ModifyAlarmPolicyNotice,
                build_notice_request(models, p, current["PolicyId"]),
            )
        if tasks_drift:
            module.sdk_call(
                client.ModifyAlarmPolicyTasks,
                build_tasks_request(models, p, current["PolicyId"]),
            )
        current = wait_for_policy(
            module, client, models, current["PolicyId"], None, p["module"], desired,
        )
        module.exit_json(
            changed=True, **(diff or {}), policy=current, msg="Alarm policy updated"
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
