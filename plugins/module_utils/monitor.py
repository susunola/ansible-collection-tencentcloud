# -*- coding: utf-8 -*-
"""Shared Cloud Monitor alarm-policy helpers.

The ``monitor_alarm_policy`` and ``monitor_alarm_policy_notice`` modules both
reconcile the same alarm-policy entity (conditions vs notification bindings).
These helpers centralize the SDK client bootstrap, policy lookup, request
construction and convergence checks so the two modules never import each
other (which the sanity ``import`` test forbids).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import time


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
