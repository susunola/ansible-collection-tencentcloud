#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tdmysql_ssl
short_description: Manage Tencent Cloud TDSQL MySQL SSL state
version_added: "0.14.0"
description: Reconciles instance SSL enablement and waits for both the asynchronous Flow and final SSL state.
options:
  instance_id: {type: str, required: true, description: Stable TDSQL MySQL instance ID.}
  enabled: {type: bool, required: true, description: Desired SSL state.}
  wait: {type: bool, default: true, description: Wait for SSL convergence.}
  waiter_delay: {type: int, default: 5, description: Seconds between checks.}
  waiter_timeout: {type: int, default: 600, description: Overall convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmysql_ssl:
    instance_id: tdsql3-xxxxxxxx
    enabled: true
"""
RETURN = r"""
ssl: {description: Effective SSL state., type: dict, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.tdmysql.v20211122 import models, tdmysql_client

    return models, tdmysql_client


def describe_request(models, instance_id):
    request = models.DescribeInstanceSSLStatusRequest()
    request.InstanceId = instance_id
    return request


def modify_request(models, instance_id, enabled):
    request = models.ModifyInstanceSSLStatusRequest()
    request.InstanceId, request.Enabled = instance_id, enabled
    return request


def flow_request(models, flow_id):
    request = models.DescribeFlowRequest()
    request.FlowId = flow_id
    return request


def get(module, client, models, instance_id):
    response = module.sdk_call(client.DescribeInstanceSSLStatus, describe_request(models, instance_id))
    return {"InstanceId": instance_id, "SSLStatus": response.SSLStatus}


def wait_ssl(module, client, models, p, flow_id, desired):
    flow_done = [False]

    def poll():
        if not flow_done[0]:
            response = module.sdk_call(client.DescribeFlow, flow_request(models, flow_id))
            status = str(response.Status or "").lower()
            if status in ("failed", "paused"):
                module.fail_json(msg="TDSQL MySQL SSL operation failed", flow_id=flow_id, status=status)
            flow_done[0] = status == "success"
        state = str(get(module, client, models, p["instance_id"])["SSLStatus"] or "").lower()
        return state if flow_done[0] else "flow_running"

    wait_for_state(module, poll, [desired], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "instance_id": {"required": True},
        "enabled": {"type": "bool", "required": True},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 600},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        current = get(module, client, models, p["instance_id"])
        desired = "enabled" if p["enabled"] else "disabled"
        if str(current["SSLStatus"] or "").lower() == desired:
            module.exit_json(changed=False, ssl=current)
        target = {"InstanceId": p["instance_id"], "SSLStatus": desired.capitalize()}
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            response = module.sdk_call(client.ModifyInstanceSSLStatus, modify_request(models, p["instance_id"], p["enabled"]))
            if p["wait"]:
                wait_ssl(module, client, models, p, response.FlowId, desired)
            current = get(module, client, models, p["instance_id"])
        module.exit_json(changed=True, **(diff_value or {}), ssl=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
