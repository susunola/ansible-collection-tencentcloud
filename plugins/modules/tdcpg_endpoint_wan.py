#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tdcpg_endpoint_wan
short_description: Manage public access for a TDSQL-C PostgreSQL endpoint
version_added: "0.14.0"
description: Opens or closes endpoint public access and waits for observable endpoint convergence.
options:
  cluster_id: {type: str, required: true, description: Cluster ID.}
  endpoint_id: {type: str, required: true, description: Endpoint ID.}
  state: {type: str, choices: [open, closed], default: closed, description: Desired public access state.}

  waiter_delay: {type: int, default: 5, description: Polling interval.}
  waiter_timeout: {type: int, default: 180, description: Convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdcpg_endpoint_wan:
    cluster_id: tdcpg-xxxxxxxx
    endpoint_id: tdcpg-ep-xxxxxxxx
    state: closed
"""
RETURN = r"""endpoint: {description: Effective endpoint metadata., type: dict, returned: always}"""
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tdcpg.v20211118 import models, tdcpg_client

    return models, tdcpg_client


def describe_request(models, cluster_id):
    r = models.DescribeClusterEndpointsRequest()
    r.ClusterId = cluster_id
    return r


def update_request(models, p):
    r = models.ModifyClusterEndpointWanStatusRequest()
    r.ClusterId, r.EndpointId, r.WanStatus = p["cluster_id"], p["endpoint_id"], "OPEN" if p["state"] == "open" else "CLOSE"
    return r


def find(module, client, models, p):
    values = module.sdk_call(client.DescribeClusterEndpoints, describe_request(models, p["cluster_id"])).EndpointSet or []
    matches = [x._serialize(allow_none=True) for x in values if x.EndpointId == p["endpoint_id"]]
    if not matches:
        module.fail_json(msg="TDSQL-C PostgreSQL endpoint was not found", endpoint_id=p["endpoint_id"])
    return matches[0]


def is_open(value):
    return bool(value.get("WanIp") or value.get("WanDomain"))


def wait(module, client, models, p, target):
    deadline = time.time() + p["waiter_timeout"]
    while True:
        value = find(module, client, models, p)
        if is_open(value) == target:
            return value
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for endpoint public access convergence", endpoint=value, expected_open=target)
        time.sleep(p["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={"cluster_id": {"required": True}, "endpoint_id": {"required": True}, "state": {"choices": ["open", "closed"], "default": "closed"}},
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdcpgClient, "tdcpg.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        target = p["state"] == "open"
        if is_open(current) == target:
            module.exit_json(changed=False, endpoint=current)
        diff = maybe_diff(module, {"open": is_open(current)}, {"open": target})
        if not module.check_mode:
            module.sdk_call(client.ModifyClusterEndpointWanStatus, update_request(models, p))
            current = wait(module, client, models, p, target)
        module.exit_json(changed=True, **(diff or {}), endpoint=current if not module.check_mode else {"EndpointId": p["endpoint_id"], "Open": target})
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
