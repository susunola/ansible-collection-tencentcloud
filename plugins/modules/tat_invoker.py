#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tat_invoker
short_description: Manage Tencent Cloud TAT scheduled invokers
version_added: "0.14.0"
description: Creates, updates, enables, disables and deletes a scheduled TAT command invoker.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  invoker_id: {type: str, description: Existing invoker ID; preferred for rename and deletion.}
  name: {type: str, description: Invoker name.}
  command_id: {type: str, description: Existing TAT command ID.}
  instance_ids: {type: list, elements: str, default: [], description: "Exact set of target CVM, Lighthouse or managed instance IDs."}
  username: {type: str, description: Operating-system user used to run the command.}
  parameters: {type: dict, default: {}, description: Command parameter values encoded as canonical JSON.}
  policy: {type: str, choices: [ONCE, RECURRENCE], default: RECURRENCE, description: One-time or recurring schedule policy.}
  recurrence: {type: str, description: Five-field crontab expression interpreted in Beijing time.}
  invoke_time: {type: str, description: ISO8601 execution time required for an ONCE policy.}
  enabled: {type: bool, default: true, description: Whether the invoker is active.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tat_invoker:
    name: nightly-maintenance
    command_id: cmd-xxxxxxxx
    instance_ids: [ins-xxxxxxxx, ins-yyyyyyyy]
    username: root
    policy: RECURRENCE
    recurrence: 0 2 * * *
    parameters:
      environment: production
"""
RETURN = r"""invoker: {description: TAT invoker metadata with command parameters redacted., type: dict, returned: always}"""
import hashlib
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tat.v20201028 import models, tat_client

    return models, tat_client


def _json(value):
    if not value:
        return "{}"
    if isinstance(value, str):
        value = json.loads(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _schedule(models, p):
    value = models.ScheduleSettings()
    value.Policy, value.Recurrence, value.InvokeTime = p["policy"], p.get("recurrence"), p.get("invoke_time")
    return value


def describe_request(models, p, offset=0):
    request = models.DescribeInvokersRequest()
    request.Offset, request.Limit = offset, 100
    if p.get("invoker_id"):
        request.InvokerIds = [p["invoker_id"]]
    return request


def _apply(request, models, p, invoker_id=None):
    request.Name, request.Type, request.CommandId = p["name"], "SCHEDULE", p["command_id"]
    request.InstanceIds, request.Username, request.Parameters = sorted(p["instance_ids"]), p.get("username"), _json(p["parameters"])
    request.ScheduleSettings = _schedule(models, p)
    if invoker_id is not None:
        request.InvokerId = invoker_id
    return request


def create_request(models, p):
    return _apply(models.CreateInvokerRequest(), models, p)


def update_request(models, p, invoker_id):
    return _apply(models.ModifyInvokerRequest(), models, p, invoker_id)


def delete_request(models, invoker_id):
    request = models.DeleteInvokerRequest()
    request.InvokerId = invoker_id
    return request


def enable_request(models, invoker_id, enabled):
    request = models.EnableInvokerRequest() if enabled else models.DisableInvokerRequest()
    request.InvokerId = invoker_id
    return request


def _schedule_dict(value):
    value = value or {}
    return {"Policy": value.get("Policy"), "Recurrence": value.get("Recurrence"), "InvokeTime": value.get("InvokeTime")}


def comparable(value):
    return {
        "Name": value.get("Name"),
        "Type": value.get("Type"),
        "CommandId": value.get("CommandId"),
        "InstanceIds": sorted(value.get("InstanceIds") or []),
        "Username": value.get("Username") or None,
        "ParametersSha256": _digest(value.get("Parameters")),
        "ScheduleSettings": _schedule_dict(value.get("ScheduleSettings")),
        "Enable": bool(value.get("Enable")),
    }


def desired(p):
    return {
        "Name": p["name"],
        "Type": "SCHEDULE",
        "CommandId": p["command_id"],
        "InstanceIds": sorted(p["instance_ids"]),
        "Username": p.get("username"),
        "ParametersSha256": _digest(p["parameters"]),
        "ScheduleSettings": {"Policy": p["policy"], "Recurrence": p.get("recurrence"), "InvokeTime": p.get("invoke_time")},
        "Enable": p["enabled"],
    }


def scrub(value):
    if not value:
        return value
    result = dict(value)
    result["Parameters"] = "<redacted>"
    return result


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeInvokers, describe_request(models, p, offset))
        values = list(response.InvokerSet or [])
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("invoker_id") and value.get("InvokerId") == p["invoker_id"]) or (not p.get("invoker_id") and value.get("Name") == p.get("name")):
                matches.append(value)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TAT invokers matched; specify invoker_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "invoker_id": {},
            "name": {},
            "command_id": {},
            "instance_ids": {"type": "list", "elements": "str", "default": []},
            "username": {},
            "parameters": {"type": "dict", "default": {}, "no_log": True},
            "policy": {"choices": ["ONCE", "RECURRENCE"], "default": "RECURRENCE"},
            "recurrence": {},
            "invoke_time": {},
            "enabled": {"type": "bool", "default": True},
        },
        required_one_of=[("invoker_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and (not p["name"] or not p["command_id"] or not p["instance_ids"]):
        module.fail_json(msg="name, command_id and instance_ids are required when state=present")
    if p["state"] == "present" and p["policy"] == "RECURRENCE" and not p.get("recurrence"):
        module.fail_json(msg="recurrence is required for a RECURRENCE policy")
    if p["state"] == "present" and p["policy"] == "ONCE" and not p.get("invoke_time"):
        module.fail_json(msg="invoke_time is required for an ONCE policy")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TatClient, "tat.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, invoker=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode:
                module.sdk_call(client.DeleteInvoker, delete_request(models, current["InvokerId"]))
            module.exit_json(changed=True, **(diff or {}), invoker=scrub(current) if module.check_mode else None)
        target = desired(p)
        before = comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, invoker=scrub(current))
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                invoker_id = current["InvokerId"]
                module.sdk_call(client.ModifyInvoker, update_request(models, p, invoker_id))
            else:
                invoker_id = module.sdk_call(client.CreateInvoker, create_request(models, p)).InvokerId
                p["invoker_id"] = invoker_id
            if not current or bool(current.get("Enable")) != p["enabled"]:
                operation = client.EnableInvoker if p["enabled"] else client.DisableInvoker
                module.sdk_call(operation, enable_request(models, invoker_id, p["enabled"]))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), invoker=scrub(current))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
