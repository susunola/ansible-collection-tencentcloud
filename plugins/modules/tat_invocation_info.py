#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tat_invocation_info
short_description: Gather Tencent Cloud TAT invocations and instance tasks
version_added: "0.14.0"
description:
  - Returns an exact invocation with its instance tasks or a bounded invocation inventory.
  - Command content and parameter values are always redacted; task output is opt-in.
options:
  invocation_id:
    description:
      - Exact invocation ID.
    type: str
  command_id:
    description:
      - Command ID filter in list mode.
    type: str
  instance_kind:
    description:
      - Instance-kind filter in list mode.
    type: str
    choices: [CVM, LIGHTHOUSE]
  include_tasks:
    description:
      - Return per-instance tasks in exact mode.
    type: bool
    default: true
  include_output:
    description:
      - Return task output; use task-level C(no_log=true) when enabled.
    type: bool
    default: false
  page_size:
    description:
      - Results per API request, from 1 through 100.
    type: int
    default: 100
  max_pages:
    description:
      - Maximum pages fetched.
    type: int
    default: 1000

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - 'Can run in C(check_mode): the module reads the current state and
        predicts the result without issuing a write API call.'
    support: full
  idempotency:
    description:
      - 'Read-only: every run returns the current state and never changes
        the target, so a repeated run reports C(changed=false).'
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tat_invocation_info:
    invocation_id: inv-xxxxxxxx
- susunola.tencentcloud.tat_invocation_info:
    command_id: cmd-xxxxxxxx
"""
RETURN = r"""
invocation: {description: Exact redacted invocation., type: dict, returned: exact mode}
tasks: {description: Exact invocation instance tasks., type: list, elements: dict, returned: exact mode}
invocations: {description: Matching redacted invocations., type: list, elements: dict, returned: list mode}
total_count: {description: Matching invocation count., type: int, returned: list mode}
truncated: {description: Whether max_pages stopped pagination., type: bool, returned: list mode}
request_id: {description: Last Tencent Cloud request ID., type: str, returned: always}
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.tat.v20201028 import models, tat_client

    return models, tat_client


def filters(models, values):
    result = []
    for name, items in values:
        if items:
            item = models.Filter()
            item.Name, item.Values = name, items if isinstance(items, list) else [items]
            result.append(item)
    return result


def invocation_request(models, p, offset):
    request = models.DescribeInvocationsRequest()
    request.Offset, request.Limit = offset, p["page_size"]
    if p.get("invocation_id"):
        request.InvocationIds = [p["invocation_id"]]
    else:
        request.Filters = filters(models, (("command-id", p.get("command_id")), ("instance-kind", p.get("instance_kind"))))
    return request


def task_request(models, p, offset):
    request = models.DescribeInvocationTasksRequest()
    request.Offset, request.Limit, request.HideOutput = offset, p["page_size"], not p["include_output"]
    request.Filters = filters(models, (("invocation-id", p["invocation_id"]),))
    return request


def scrub(value, include_output=False):
    result = dict(value)
    result["Parameters"], result["DefaultParameters"], result["CommandContent"] = "<redacted>", "<redacted>", "<redacted>"
    result.pop("CommandDocument", None)
    if not include_output and result.get("TaskResult"):
        result["TaskResult"] = {"Output": "<redacted>"}
    return result


def pages(module, operation, build, item_name, p):
    values, total, offset, request_id, truncated = [], 0, 0, None, False
    for _ in range(p["max_pages"]):
        response = module.sdk_call(operation, build(offset))
        items = list(getattr(response, item_name) or [])
        values.extend(item._serialize(allow_none=True) for item in items)
        total, request_id = int(response.TotalCount or 0), response.RequestId
        offset += len(items)
        if not items or offset >= total:
            break
    else:
        truncated = True
    return values, total, truncated, request_id


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "invocation_id": {},
            "command_id": {},
            "instance_kind": {"choices": ["CVM", "LIGHTHOUSE"]},
            "include_tasks": {"type": "bool", "default": True},
            "include_output": {"type": "bool", "default": False},
            "page_size": {"type": "int", "default": 100},
            "max_pages": {"type": "int", "default": 1000},
        },
        supports_check_mode=True,
        mutually_exclusive=[("invocation_id", "command_id"), ("invocation_id", "instance_kind")],
    )
    p = module.params
    if not 1 <= p["page_size"] <= 100 or not 1 <= p["max_pages"] <= 1000:
        module.fail_json(msg="page_size and max_pages are outside supported bounds")
    if p["include_output"] and not p.get("invocation_id"):
        module.fail_json(msg="include_output requires exact invocation_id mode")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TatClient, "tat.tencentcloudapi.com")
    try:
        values, total, truncated, request_id = pages(
            module, client.DescribeInvocations, lambda offset: invocation_request(models, p, offset), "InvocationSet", p
        )
        values = [scrub(value) for value in values]
        if p.get("invocation_id"):
            invocation = values[0] if values else None
            tasks = []
            if invocation and p["include_tasks"]:
                tasks, _, _, request_id = pages(module, client.DescribeInvocationTasks, lambda offset: task_request(models, p, offset), "InvocationTaskSet", p)
                tasks = [scrub(value, p["include_output"]) for value in tasks]
            module.exit_json(changed=False, invocation=invocation, tasks=tasks, request_id=request_id)
        module.exit_json(changed=False, invocations=values, total_count=total, truncated=truncated, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
