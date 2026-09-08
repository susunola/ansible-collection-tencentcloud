#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tdcpg_instance_state
short_description: Manage TDSQL-C PostgreSQL instance runtime state
version_added: "0.14.0"
description: Isolates or recovers cluster instances, or performs an explicitly requested restart.
options:
  cluster_id: {type: str, required: true, description: Cluster ID.}
  instance_ids: {type: list, elements: str, required: true, description: Exact instances to operate on.}
  state: {type: str, choices: [running, isolated, restarted], required: true, description: Desired action or state.}
  period_months: {type: int, default: 1, description: Recovery purchase period for prepaid instances.}

  waiter_delay: {type: int, default: 5, description: Polling interval.}
  waiter_timeout: {type: int, default: 300, description: Convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdcpg_instance_state:
    cluster_id: tdcpg-xxxxxxxx
    instance_ids: [tdcpg-ins-xxxxxxxx]
    state: running
"""
RETURN = r"""instances: {description: Effective selected instance metadata., type: list, elements: dict, returned: always}"""
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tdcpg.v20211118 import models, tdcpg_client

    return models, tdcpg_client


def describe_request(models, p):
    r = models.DescribeClusterInstancesRequest()
    r.ClusterId, r.PageNumber, r.PageSize = p["cluster_id"], 1, 100
    return r


def action_request(cls, p):
    r = cls()
    r.ClusterId, r.InstanceIdSet = p["cluster_id"], p["instance_ids"]
    return r


def recover_request(models, p):
    r = action_request(models.RecoverClusterInstancesRequest, p)
    r.Period = p["period_months"]
    return r


def selected(module, client, models, p):
    values = module.sdk_call(client.DescribeClusterInstances, describe_request(models, p)).InstanceSet or []
    by_id = {x.InstanceId: x._serialize(allow_none=True) for x in values}
    missing = sorted(set(p["instance_ids"]) - set(by_id))
    if missing:
        module.fail_json(msg="TDSQL-C PostgreSQL instances were not found", missing=missing)
    return [by_id[x] for x in p["instance_ids"]]


def status(value):
    return str(value.get("Status") or "").lower()


def wait(module, client, models, p, target):
    deadline = time.time() + p["waiter_timeout"]
    while True:
        values = selected(module, client, models, p)
        if all(status(x) == target for x in values):
            return values
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for instance state convergence", instances=values, expected=target)
        time.sleep(p["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "cluster_id": {"required": True},
            "instance_ids": {"type": "list", "elements": "str", "required": True},
            "state": {"choices": ["running", "isolated", "restarted"], "required": True},
            "period_months": {"type": "int", "default": 1},
        },
        supports_check_mode=True,
    )
    p = module.params
    if not p["instance_ids"] or len(p["instance_ids"]) != len(set(p["instance_ids"])):
        module.fail_json(msg="instance_ids must be a non-empty unique list")
    if p["state"] == "restarted" and len(p["instance_ids"]) != 1:
        module.fail_json(msg="TDSQL-C PostgreSQL supports restarting one instance per request")
    if p["period_months"] < 1 or p["period_months"] > 60:
        module.fail_json(msg="period_months must be between 1 and 60")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdcpgClient, "tdcpg.tencentcloudapi.com")
    try:
        values = selected(module, client, models, p)
        target = "running" if p["state"] == "restarted" else p["state"]
        if p["state"] != "restarted" and all(status(x) == target for x in values):
            module.exit_json(changed=False, instances=values)
        diff = maybe_diff(
            module, [{"InstanceId": x["InstanceId"], "Status": status(x)} for x in values], [{"InstanceId": x, "Status": target} for x in p["instance_ids"]]
        )
        if not module.check_mode:
            if p["state"] == "isolated":
                module.sdk_call(client.IsolateClusterInstances, action_request(models.IsolateClusterInstancesRequest, p))
            elif p["state"] == "running":
                module.sdk_call(client.RecoverClusterInstances, recover_request(models, p))
            else:
                module.sdk_call(client.RestartClusterInstances, action_request(models.RestartClusterInstancesRequest, p))
            values = wait(module, client, models, p, target)
        module.exit_json(changed=True, **(diff or {}), instances=values, restarted=p["state"] == "restarted")
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
