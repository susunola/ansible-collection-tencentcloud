#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: monitor_prometheus_alert_group
short_description: Manage Tencent Cloud Managed Prometheus alert groups
version_added: "0.14.0"
description: Creates, updates and deletes Prometheus alert groups and their rules.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - Prometheus instance ID.
    type: str
    required: true
  group_id:
    description:
      - Existing alert-group ID.
    type: str
  name:
    description:
      - Alert-group name.
    type: str
  enabled:
    description:
      - Enable every rule in the group.
    type: bool
    default: true
  receivers:
    description:
      - Alarm notification template IDs.
    type: list
    default: []
    elements: str
  custom_receiver:
    description:
      - SDK-compatible custom receiver.
    type: dict
  repeat_interval:
    description:
      - Notification repeat interval.
    type: str
    default: 1h
  rules:
    description:
      - SDK-compatible alert rules.
    type: list
    default: []
    elements: dict

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.monitor_prometheus_alert_group:
    instance_id: prom-xxxxxxxx
    name: application-alerts
    receivers: [notice-xxxxxxxx]
    rules:
      - {RuleName: high-error-rate, Expr: 'rate(errors_total[5m]) > 1', Duration: 5m, State: 2}
"""
RETURN = r"""alert_group: {description: Prometheus alert-group metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.monitor.v20180724 import models, monitor_client

    return models, monitor_client


def build_describe(models, p, offset=0):
    request = models.DescribePrometheusAlertGroupsRequest()
    request.InstanceId, request.GroupId = p["instance_id"], p.get("group_id")
    request.GroupName = p.get("name") if not p.get("group_id") else None
    request.Offset, request.Limit = offset, 100
    return request


def _model(models, name, value):
    item = getattr(models, name)()
    item._deserialize(value)
    return item


def apply(request, models, p, group_id=None):
    request.InstanceId, request.GroupName, request.GroupState = p["instance_id"], p["name"], 2 if p["enabled"] else 3
    request.AMPReceivers, request.RepeatInterval = p["receivers"], p["repeat_interval"]
    request.Rules = [_model(models, "PrometheusAlertGroupRuleSet", x) for x in p["rules"]]
    if p.get("custom_receiver") is not None:
        request.CustomReceiver = _model(models, "PrometheusAlertCustomReceiver", p["custom_receiver"])
    if group_id:
        request.GroupId = group_id
    return request


def build_create(models, p):
    return apply(models.CreatePrometheusAlertGroupRequest(), models, p)


def build_update(models, p, group_id):
    return apply(models.UpdatePrometheusAlertGroupRequest(), models, p, group_id)


def build_delete(models, instance_id, group_id):
    request = models.DeletePrometheusAlertGroupsRequest()
    request.InstanceId, request.GroupIds = instance_id, [group_id]
    return request


def find(module, client, models, p):
    matches, offset = [], 0
    while True:
        response = module.sdk_call(client.DescribePrometheusAlertGroups, build_describe(models, p, offset))
        page = list(response.AlertGroupSet or [])
        for item in page:
            value = item._serialize(allow_none=True)
            if (p.get("group_id") and value.get("GroupId") == p["group_id"]) or (not p.get("group_id") and value.get("GroupName") == p.get("name")):
                matches.append(value)
        offset += len(page)
        total = getattr(response, "TotalCount", None)
        if not page or (total is not None and offset >= total) or (total is None and len(page) < 100):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple Prometheus alert groups have the requested name", name=p.get("name"))
    return matches[0] if matches else None


def desired(p):
    return {
        "GroupName": p["name"],
        "AMPReceivers": p["receivers"],
        "CustomReceiver": p.get("custom_receiver"),
        "RepeatInterval": p["repeat_interval"],
        "Rules": p["rules"],
    }


def comparable(v):
    return {
        "GroupName": v.get("GroupName"),
        "AMPReceivers": v.get("AMPReceivers") or [],
        "CustomReceiver": v.get("CustomReceiver"),
        "RepeatInterval": v.get("RepeatInterval") or "1h",
        "Rules": v.get("Rules") or [],
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "group_id": {},
            "name": {},
            "enabled": {"type": "bool", "default": True},
            "receivers": {"type": "list", "elements": "str", "default": []},
            "custom_receiver": {"type": "dict"},
            "repeat_interval": {"default": "1h"},
            "rules": {"type": "list", "elements": "dict", "default": []},
        },
        required_one_of=[("group_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, alert_group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeletePrometheusAlertGroups, build_delete(models, p["instance_id"], current["GroupId"]))
            module.exit_json(changed=True, **(diff or {}), alert_group=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, alert_group=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.UpdatePrometheusAlertGroup, build_update(models, p, current["GroupId"]))
                p["group_id"] = current["GroupId"]
            else:
                p["group_id"] = module.sdk_call(client.CreatePrometheusAlertGroup, build_create(models, p)).GroupId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), alert_group=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
