#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tat_invocation
short_description: Invoke or cancel a Tencent Cloud TAT command
version_added: "0.14.0"
description:
  - Starts a reusable TAT command on up to 200 instances and optionally waits for every instance task.
  - This is an action module; C(state=started) creates a new invocation on every execution.
  - Parameters and command content are redacted from output. Task output is hidden unless explicitly requested.
options:
  state: {type: str, choices: [started, cancelled], default: started, description: Start a new invocation or cancel an existing one.}
  invocation_id: {type: str, description: Existing invocation ID required for cancellation.}
  command_id: {type: str, description: Reusable command ID required when starting.}
  instance_ids: {type: list, elements: str, default: [], description: Target CVM, Lighthouse or managed instance IDs, up to 200.}
  parameters: {type: dict, default: {}, description: Command placeholder values.}
  username: {type: str, description: Least-privilege operating-system user override.}
  working_directory: {type: str, description: Working-directory override.}
  timeout: {type: int, description: Command timeout override from 1 through 86400 seconds.}
  output_cos_bucket_url: {type: str, description: HTTPS COS bucket URL for full logs.}
  output_cos_key_prefix: {type: str, description: COS key prefix for logs.}
  wait: {type: bool, default: true, description: Wait for all instance tasks to reach terminal states.}
  fail_on_task_error: {type: bool, default: true, description: Fail when any task is unsuccessful.}
  include_output: {type: bool, default: false, description: Return task output; use task-level C(no_log=true) when enabled.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  waiter_delay: {type: int, default: 5, description: Polling interval.}
  waiter_timeout: {type: int, default: 900, description: Overall execution wait timeout.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tat_invocation:
    command_id: cmd-xxxxxxxx
    instance_ids: [ins-xxxxxxxx, ins-yyyyyyyy]
    username: deploy
    parameters: {release: '2026.09'}
"""
RETURN = r"""
invocation_id: {description: TAT invocation ID., type: str, returned: always}
tasks: {description: Per-instance task results with sensitive command data redacted., type: list, elements: dict, returned: when waiting}
status_summary: {description: Counts keyed by terminal task status., type: dict, returned: when waiting}
"""
import json
import time
from collections import Counter
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload

TERMINAL = {"SUCCESS", "DELIVER_FAILED", "START_FAILED", "FAILED", "TIMEOUT", "TASK_TIMEOUT", "CANCELLED", "TERMINATED"}
FAILED = TERMINAL - {"SUCCESS"}


def _load():
    from tencentcloud.tat.v20201028 import models, tat_client

    return models, tat_client


def invoke_request(models, p):
    request = models.InvokeCommandRequest()
    request.CommandId, request.InstanceIds = p["command_id"], sorted(set(p["instance_ids"]))
    request.Parameters = json.dumps({str(k): str(v) for k, v in p["parameters"].items()}, sort_keys=True, separators=(",", ":"))
    for source, target in (
        ("username", "Username"),
        ("working_directory", "WorkingDirectory"),
        ("timeout", "Timeout"),
        ("output_cos_bucket_url", "OutputCOSBucketUrl"),
        ("output_cos_key_prefix", "OutputCOSKeyPrefix"),
    ):
        if p.get(source) is not None:
            setattr(request, target, p[source])
    return request


def cancel_request(models, p):
    request = models.CancelInvocationRequest()
    request.InvocationId = p["invocation_id"]
    if p["instance_ids"]:
        request.InstanceIds = sorted(set(p["instance_ids"]))
    return request


def tasks_request(models, invocation_id, offset, include_output):
    request = models.DescribeInvocationTasksRequest()
    request.Offset, request.Limit, request.HideOutput = offset, 100, not include_output
    item = models.Filter()
    item.Name, item.Values = "invocation-id", [invocation_id]
    request.Filters = [item]
    return request


def read_tasks(module, client, models, invocation_id, include_output):
    offset, values = 0, []
    while True:
        response = module.sdk_call(client.DescribeInvocationTasks, tasks_request(models, invocation_id, offset, include_output))
        items = list(response.InvocationTaskSet or [])
        values.extend(item._serialize(allow_none=True) for item in items)
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            break
    for value in values:
        value.pop("CommandDocument", None)
        if not include_output and value.get("TaskResult"):
            value["TaskResult"] = {"Output": "<redacted>"}
    return values


def wait_tasks(module, client, models, invocation_id, expected_count, include_output):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        values = read_tasks(module, client, models, invocation_id, include_output)
        if len(values) >= expected_count and all(value.get("TaskStatus") in TERMINAL for value in values):
            return values
        if time.time() >= deadline:
            module.fail_json(
                msg="Timed out waiting for TAT invocation tasks", invocation_id=invocation_id, observed_tasks=len(values), expected_tasks=expected_count
            )
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["started", "cancelled"], "default": "started"},
            "invocation_id": {},
            "command_id": {},
            "instance_ids": {"type": "list", "elements": "str", "default": []},
            "parameters": {"type": "dict", "default": {}, "no_log": True},
            "username": {},
            "working_directory": {},
            "timeout": {"type": "int"},
            "output_cos_bucket_url": {},
            "output_cos_key_prefix": {},
            "wait": {"type": "bool", "default": True},
            "fail_on_task_error": {"type": "bool", "default": True},
            "include_output": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "started" and (not p.get("command_id") or not p["instance_ids"]):
        module.fail_json(msg="command_id and instance_ids are required when state=started")
    if p["state"] == "cancelled" and not p.get("invocation_id"):
        module.fail_json(msg="invocation_id is required when state=cancelled")
    if len(p["instance_ids"]) > 200:
        module.fail_json(msg="instance_ids cannot contain more than 200 targets")
    if p.get("timeout") is not None and not 1 <= p["timeout"] <= 86400:
        module.fail_json(msg="timeout must be between 1 and 86400 seconds")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TatClient, "tat.tencentcloudapi.com")
    try:
        if module.check_mode:
            module.exit_json(changed=True, invocation_id=p.get("invocation_id"), tasks=[])
        if p["state"] == "cancelled":
            module.sdk_call(client.CancelInvocation, cancel_request(models, p))
            module.exit_json(changed=True, invocation_id=p["invocation_id"], tasks=[])
        invocation_id = module.sdk_call(client.InvokeCommand, invoke_request(models, p)).InvocationId
        if not p["wait"]:
            module.exit_json(changed=True, invocation_id=invocation_id, tasks=[])
        values = wait_tasks(module, client, models, invocation_id, len(set(p["instance_ids"])), p["include_output"])
        summary = dict(Counter(value.get("TaskStatus") for value in values))
        failures = [value for value in values if value.get("TaskStatus") in FAILED]
        if failures and p["fail_on_task_error"]:
            module.fail_json(msg="One or more TAT invocation tasks failed", invocation_id=invocation_id, status_summary=summary, failed_tasks=failures)
        module.exit_json(changed=True, invocation_id=invocation_id, tasks=values, status_summary=summary)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
