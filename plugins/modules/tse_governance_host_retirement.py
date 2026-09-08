#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_governance_host_retirement
short_description: Retire all Tencent Cloud TSE governance instances on a host
version_added: "0.14.0"
description: Discovers every governance service instance registered on one host, removes them in batches and waits for the host to become empty.
options:
  state: {type: str, choices: [absent], default: absent, description: Desired host registration state.}
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
  host: {type: str, required: true, description: Host or IP whose governance registrations must be removed.}
  batch_size: {type: int, default: 100, description: Maximum registrations deleted per API request.}
  waiter_delay: {type: int, default: 2, description: Polling interval while waiting for convergence.}
  waiter_timeout: {type: int, default: 60, description: Maximum convergence wait.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_governance_host_retirement:
    instance_id: ins-xxxxxxxx
    host: 10.0.0.30
    state: absent
'''
RETURN = r'''
removed_instances: {description: Governance instances discovered before retirement., type: list, elements: dict, returned: always}
host: {description: Retired host identity., type: str, returned: always}
'''

import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client
    return models, tse_client


def describe_request(models, params, offset):
    value = models.DescribeGovernanceInstancesRequest()
    value.InstanceId, value.Host = params["instance_id"], params["host"]
    value.Offset, value.Limit = offset, 100
    return value


def find_all(module, client, models, params):
    values, offset, total = [], 0, None
    while total is None or offset < total:
        response = module.sdk_call(client.DescribeGovernanceInstances, describe_request(models, params, offset))
        page = response.Content or []
        values.extend(item._serialize(allow_none=True) for item in page if item.Host == params["host"])
        total = response.TotalCount
        offset += len(page)
        if not page:
            break
    return values


def delete_request(models, params, instances):
    value = models.DeleteGovernanceInstancesByHostRequest()
    value.InstanceId, value.GovernanceInstances = params["instance_id"], []
    for selected in instances:
        item = models.GovernanceInstanceUpdate()
        item.from_json_string(json.dumps(selected))
        value.GovernanceInstances.append(item)
    return value


def batches(values, size):
    for offset in range(0, len(values), size):
        yield values[offset:offset + size]


def wait(module, client, models, params):
    deadline = time.time() + params["waiter_timeout"]
    while True:
        current = find_all(module, client, models, params)
        if not current:
            return
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TSE governance host retirement", host=params["host"],
                             remaining_instances=current)
        time.sleep(params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["absent"], "default": "absent"},
        "instance_id": {"required": True}, "host": {"required": True},
        "batch_size": {"type": "int", "default": 100},
        "waiter_delay": {"type": "int", "default": 2}, "waiter_timeout": {"type": "int", "default": 60},
    }, supports_check_mode=True)
    params = module.params
    if params["batch_size"] < 1 or params["batch_size"] > 100:
        module.fail_json(msg="batch_size must be between 1 and 100")
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find_all(module, client, models, params)
        if not current:
            module.exit_json(changed=False, host=params["host"], removed_instances=[])
        diff = maybe_diff(module, current, [])
        if not module.check_mode:
            for selected in batches(current, params["batch_size"]):
                response = module.sdk_call(client.DeleteGovernanceInstancesByHost,
                                           delete_request(models, params, selected))
                if response.Result is not True:
                    module.fail_json(msg="TSE governance host retirement returned an unsuccessful result",
                                     host=params["host"])
            wait(module, client, models, params)
        module.exit_json(changed=True, **(diff or {}), host=params["host"], removed_instances=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
