#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_network_connection
short_description: Reconcile Tencent Cloud DLC network-connection metadata
version_added: "0.14.0"
description:
  - Discovers an existing DLC network connection by exact name and reconciles its description.
  - The available DLC API does not expose creation or deletion of this resource, so an absent connection is reported instead of fabricated.
options:
  name:
    description:
      - Exact network-connection name.
    type: str
    required: true
  description:
    description:
      - Desired network-connection description.
    type: str
    required: true
  data_engine_name:
    description:
      - Optional exact data-engine name used to disambiguate the connection.
    type: str
  vpc_id:
    description:
      - Optional source VPC ID used to disambiguate the connection.
    type: str
  connection_type:
    description:
      - Optional network-connection type used to disambiguate the connection.
    type: int
  wait:
    description:
      - Wait for readable description convergence.
    type: bool
    default: true
  waiter_delay:
    description:
      - Seconds between polls.
    type: int
    default: 3
  waiter_timeout:
    description:
      - Overall convergence timeout.
    type: int
    default: 180

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
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_network_connection:
    name: analytics-vpc
    data_engine_name: production-spark
    description: Production analytics data-source route
"""
RETURN = r"""
network_connection: {description: Effective DLC network-connection metadata., type: dict, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def describe_request(models, p, offset=0):
    request = models.DescribeNetworkConnectionsRequest()
    request.NetworkConnectionName, request.Offset, request.Limit = p["name"], offset, 100
    if p.get("data_engine_name") is not None:
        request.DataEngineName = p["data_engine_name"]
    if p.get("vpc_id") is not None:
        request.DatasourceConnectionVpcId = p["vpc_id"]
    if p.get("connection_type") is not None:
        request.NetworkConnectionType = p["connection_type"]
    return request


def find(module, client, models, p):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeNetworkConnections, describe_request(models, p, offset))
        page = response.NetworkConnectionSet or []
        for item in page:
            value = item._serialize(allow_none=True)
            if value.get("DatasourceConnectionName") != p["name"]:
                continue
            if p.get("data_engine_name") is not None and value.get("HouseName") != p["data_engine_name"]:
                continue
            if p.get("vpc_id") is not None and value.get("DatasourceConnectionVpcId") != p["vpc_id"]:
                continue
            if p.get("connection_type") is not None and value.get("NetworkConnectionType") != p["connection_type"]:
                continue
            matches.append(value)
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0):
            break
    if not matches:
        module.fail_json(msg="DLC network connection was not found", name=p["name"])
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC network connections matched; provide data_engine_name, vpc_id or connection_type", name=p["name"])
    return matches[0]


def update_request(models, name, description):
    request = models.UpdateNetworkConnectionRequest()
    request.NetworkConnectionName, request.NetworkConnectionDesc = name, description
    return request


def wait_connection(module, client, models, p):
    def poll():
        return "ready" if (find(module, client, models, p).get("NetworkConnectionDesc") or "") == p["description"] else "pending"

    wait_for_state(module, poll, ["ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "name": {"required": True},
        "description": {"required": True},
        "data_engine_name": {},
        "vpc_id": {},
        "connection_type": {"type": "int"},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 3},
        "waiter_timeout": {"type": "int", "default": 180},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if (current.get("NetworkConnectionDesc") or "") == p["description"]:
            module.exit_json(changed=False, network_connection=current)
        target = dict(current)
        target["NetworkConnectionDesc"] = p["description"]
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.UpdateNetworkConnection, update_request(models, p["name"], p["description"]))
            if p["wait"]:
                wait_connection(module, client, models, p)
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff_value or {}), network_connection=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
