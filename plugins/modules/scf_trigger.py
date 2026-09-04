#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: scf_trigger
short_description: Manage Tencent Cloud SCF triggers
version_added: "0.14.0"
description: Creates, enables, disables, replaces and deletes SCF function triggers.
options:
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  function_name: {type: str, required: true, description: Function name.}
  namespace: {type: str, default: default, description: Function namespace.}
  qualifier: {type: str, default: '$LATEST', description: Function version or alias.}
  name: {type: str, required: true, description: Trigger name.}
  trigger_type: {type: str, required: true, description: "Trigger type such as timer, cos, cmq or apigw."}
  trigger_desc: {type: str, description: Service-specific trigger description JSON or expression. Required when state is present.}
  enabled: {type: bool, default: true, description: Enable the trigger.}
  custom_argument: {type: str, description: Custom trigger argument.}
  description: {type: str, default: '', description: Human-readable description.}
  force_replace: {type: bool, default: false, description: Replace the trigger when immutable configuration changes.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.scf_trigger:
    function_name: rotate-logs
    name: every-hour
    trigger_type: timer
    trigger_desc: 0 0 * * * * *
"""
RETURN = r"""trigger: {description: SCF trigger metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.scf.v20180416 import models, scf_client

    return models, scf_client


def find(module, client, models, p):
    request = models.ListTriggersRequest()
    request.FunctionName, request.Namespace = p["function_name"], p["namespace"]
    request.Offset, request.Limit = 0, 100
    items = module.sdk_call(client.ListTriggers, request).Triggers or []
    matches = [x._serialize(allow_none=True) for x in items if x.TriggerName == p["name"] and x.Type == p["trigger_type"]]
    if len(matches) > 1:
        module.fail_json(msg="Multiple SCF triggers match the requested identity", name=p["name"])
    return matches[0] if matches else None


def delete_request(models, p, current=None):
    request = models.DeleteTriggerRequest()
    request.FunctionName, request.Namespace = p["function_name"], p["namespace"]
    request.Qualifier, request.TriggerName, request.Type = p["qualifier"], p["name"], p["trigger_type"]
    request.TriggerDesc = (current or {}).get("TriggerDesc") or p["trigger_desc"]
    return request


def wanted(p):
    return {
        "Enable": "OPEN" if p["enabled"] else "CLOSE",
        "Qualifier": p["qualifier"],
        "TriggerName": p["name"],
        "Type": p["trigger_type"],
        "TriggerDesc": p["trigger_desc"],
        "CustomArgument": p["custom_argument"],
        "Description": p["description"],
    }


def create(module, client, models, p):
    request = models.CreateTriggerRequest()
    request.FunctionName, request.Namespace = p["function_name"], p["namespace"]
    request.Qualifier, request.TriggerName, request.Type = p["qualifier"], p["name"], p["trigger_type"]
    request.TriggerDesc, request.Enable = p["trigger_desc"], "OPEN" if p["enabled"] else "CLOSE"
    request.CustomArgument, request.Description = p["custom_argument"], p["description"]
    module.sdk_call(client.CreateTrigger, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "function_name": {"required": True},
            "namespace": {"default": "default"},
            "qualifier": {"default": "$LATEST"},
            "name": {"required": True},
            "trigger_type": {"required": True},
            "trigger_desc": {},
            "enabled": {"type": "bool", "default": True},
            "custom_argument": {},
            "description": {"default": ""},
            "force_replace": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["trigger_desc"]:
        module.fail_json(msg="trigger_desc is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ScfClient, "scf.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, trigger=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteTrigger, delete_request(models, p, current))
            module.exit_json(changed=True, **(diff or {}), trigger=current if module.check_mode else None)
        target = wanted(p)
        before = {k: current.get(k) for k in target} if current else None
        if before == target:
            module.exit_json(changed=False, trigger=current)
        immutable = current and any(before[k] != target[k] for k in ("Qualifier", "TriggerDesc", "CustomArgument", "Description"))
        if immutable and not p["force_replace"]:
            module.fail_json(msg="SCF trigger configuration is immutable; set force_replace=true", trigger=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if immutable:
                module.sdk_call(client.DeleteTrigger, delete_request(models, p, current))
                create(module, client, models, p)
            elif current:
                request = models.UpdateTriggerStatusRequest()
                request.Enable = "OPEN" if p["enabled"] else "CLOSE"
                request.FunctionName, request.Namespace, request.Qualifier = p["function_name"], p["namespace"], p["qualifier"]
                request.TriggerName, request.Type, request.TriggerDesc = p["name"], p["trigger_type"], p["trigger_desc"]
                module.sdk_call(client.UpdateTriggerStatus, request)
            else:
                create(module, client, models, p)
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), trigger=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
