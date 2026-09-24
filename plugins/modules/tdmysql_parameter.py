#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tdmysql_parameter
short_description: Manage Tencent Cloud TDSQL MySQL instance parameters
version_added: "0.14.0"
description:
  - Reconciles a partial map of instance parameter names and values while preserving unspecified parameters.
  - Unknown parameter names are rejected before mutation and asynchronous changes wait on their task Flow.
options:
  instance_id:
    description:
      - Stable TDSQL MySQL instance ID.
    type: str
    required: true
  parameters:
    description:
      - Parameter names mapped to complete desired string-compatible values.
    type: dict
    required: true
  wait:
    description:
      - Wait for asynchronous parameter application.
    type: bool
    default: true
  waiter_delay:
    description:
      - Seconds between Flow checks.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Overall Flow timeout.
    type: int
    default: 600

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
- susunola.tencentcloud.tdmysql_parameter:
    instance_id: tdsql3-xxxxxxxx
    parameters:
      max_connections: '1000'
      slow_query_log: 'ON'
"""
RETURN = r"""
parameters: {description: Effective requested parameters including constraints and restart requirements., type: dict, returned: always}
restart_required: {description: Whether any changed parameter requires a restart., type: bool, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tdmysql import _load, parameter_describe_request, parameter_map, selected
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def modify_request(models, instance_id, values):
    request = models.ModifyDBParametersRequest()
    request.InstanceId = instance_id
    request.Params = []
    for name, value in sorted(values.items()):
        item = models.DBParamValue()
        item.Param, item.Value = name, str(value)
        request.Params.append(item)
    return request


def flow_request(models, task_id):
    request = models.DescribeFlowRequest()
    request.FlowId = task_id
    return request


def wait_task(module, client, models, task_id):
    def poll():
        response = module.sdk_call(client.DescribeFlow, flow_request(models, task_id))
        status = str(response.Status or "").lower()
        if status in ("failed", "paused"):
            module.fail_json(msg="TDSQL MySQL parameter task failed", task_id=task_id, status=status, request_id=response.RequestId)
        return status

    wait_for_state(module, poll, ["success"], timeout=module.params["waiter_timeout"], delay=module.params["waiter_delay"])


def read_parameters(module, client, models, instance_id):
    response = module.sdk_call(client.DescribeDBParameters, parameter_describe_request(models, instance_id))
    return parameter_map(response)


def run_module():
    spec = {
        "instance_id": {"required": True},
        "parameters": {"type": "dict", "required": True},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 600},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if not p["parameters"]:
        module.fail_json(msg="parameters must not be empty")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        all_current = read_parameters(module, client, models, p["instance_id"])
        unknown = sorted(set(p["parameters"]) - set(all_current))
        if unknown:
            module.fail_json(msg="unknown TDSQL MySQL parameter names", unknown_parameters=unknown)
        current = selected(all_current, p["parameters"])
        changes = {name: str(value) for name, value in p["parameters"].items() if str(current[name].get("Value")) != str(value)}
        restart_required = any(bool(current[name].get("NeedRestart")) for name in changes)
        if not changes:
            module.exit_json(changed=False, parameters=current, restart_required=False)
        target = {name: dict(value, Value=str(p["parameters"][name])) for name, value in current.items()}
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            response = module.sdk_call(client.ModifyDBParameters, modify_request(models, p["instance_id"], changes))
            if p["wait"]:
                wait_task(module, client, models, response.TaskID)
            current = selected(read_parameters(module, client, models, p["instance_id"]), p["parameters"])
        module.exit_json(changed=True, **(diff_value or {}), parameters=current if not module.check_mode else target, restart_required=restart_required)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
