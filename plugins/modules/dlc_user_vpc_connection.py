#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dlc_user_vpc_connection
short_description: Connect DLC engine networks to Tencent Cloud VPCs
version_added: "0.14.0"
description:
  - Creates, discovers, waits for and deletes DLC user VPC endpoint connections.
  - VPC, subnet, endpoint name, optional VIP and engine-network identity are immutable.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired connection state.}
  engine_network_id: {type: str, required: true, description: DLC engine network ID.}
  endpoint_id: {type: str, description: Existing DLC user VPC endpoint ID.}
  endpoint_name: {type: str, description: Endpoint name; required for creation and usable for discovery.}
  vpc_id: {type: str, description: User VPC ID required for creation.}
  subnet_id: {type: str, description: User subnet ID required for creation; the API does not return it after creation.}
  endpoint_vip: {type: str, description: Optional creation-time endpoint VIP; the API does not return it after creation.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize endpoint deletion.}
  wait: {type: bool, default: true, description: Wait for presence or absence convergence.}
  waiter_delay: {type: int, default: 5, description: Seconds between convergence polls.}
  waiter_timeout: {type: int, default: 300, description: Overall convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_user_vpc_connection:
    engine_network_id: engine-network-xxxxxxxx
    endpoint_name: analytics-endpoint
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx

- susunola.tencentcloud.dlc_user_vpc_connection:
    engine_network_id: engine-network-xxxxxxxx
    endpoint_id: vpce-xxxxxxxx
    state: absent
    allow_delete: true
"""
RETURN = r"""connection: {description: Effective DLC user VPC connection metadata., type: dict, returned: always}
endpoint_id: {description: DLC user VPC endpoint ID., type: str, returned: when present}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def describe_request(models, engine_network_id, endpoint_id=None):
    request = models.DescribeUserVpcConnectionRequest()
    request.EngineNetworkId = engine_network_id
    if endpoint_id:
        request.UserVpcEndpointIds = [endpoint_id]
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeUserVpcConnection, describe_request(models, p["engine_network_id"], p.get("endpoint_id")))
    values = [x._serialize(allow_none=True) for x in response.UserVpcConnectionInfos or []]
    if p.get("endpoint_id"):
        matches = [x for x in values if x.get("UserVpcEndpointId") == p["endpoint_id"]]
    else:
        matches = [x for x in values if x.get("UserVpcEndpointName") == p.get("endpoint_name")]
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC VPC connections matched; specify endpoint_id")
    return matches[0] if matches else None


def create_request(models, p):
    request = models.CreateUserVpcConnectionRequest()
    request.EngineNetworkId, request.UserVpcId = p["engine_network_id"], p["vpc_id"]
    request.UserSubnetId, request.UserVpcEndpointName = p["subnet_id"], p["endpoint_name"]
    request.UserVpcEndpointVip = p.get("endpoint_vip")
    return request


def delete_request(models, engine_network_id, endpoint_id):
    request = models.DeleteUserVpcConnectionRequest()
    request.EngineNetworkId, request.UserVpcEndpointId = engine_network_id, endpoint_id
    return request


def wait_connection(module, client, models, p, present):
    def poll():
        return "present" if find(module, client, models, p) else "absent"

    wait_for_state(module, poll, ["present" if present else "absent"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "engine_network_id": {"required": True},
        "endpoint_id": {},
        "endpoint_name": {},
        "vpc_id": {},
        "subnet_id": {},
        "endpoint_vip": {},
        "allow_delete": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 300},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("endpoint_id", "endpoint_name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, connection=None, endpoint_id=None)
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize deleting the DLC VPC connection", connection=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                p["endpoint_id"] = current["UserVpcEndpointId"]
                module.sdk_call(client.DeleteUserVpcConnection, delete_request(models, p["engine_network_id"], p["endpoint_id"]))
                if p["wait"]:
                    wait_connection(module, client, models, p, False)
            module.exit_json(changed=True, **(diff_value or {}), connection=None, endpoint_id=None)
        if not current:
            missing = [key for key in ("endpoint_name", "vpc_id", "subnet_id") if not p.get(key)]
            if missing:
                module.fail_json(msg="creation parameters are required for a DLC VPC connection", missing=missing)
            target = {"EngineNetworkId": p["engine_network_id"], "UserVpcId": p["vpc_id"], "UserVpcEndpointName": p["endpoint_name"]}
            diff_value = maybe_diff(module, None, target)
            endpoint_id = None
            if not module.check_mode:
                endpoint_id = module.sdk_call(client.CreateUserVpcConnection, create_request(models, p)).UserVpcEndpointId
                p["endpoint_id"] = endpoint_id
                if p["wait"]:
                    wait_connection(module, client, models, p, True)
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff_value or {}), connection=current if not module.check_mode else target, endpoint_id=endpoint_id)
        immutable = {"EngineNetworkId": p["engine_network_id"], "UserVpcId": p.get("vpc_id"), "UserVpcEndpointName": p.get("endpoint_name")}
        drift = {key: (current.get(key), value) for key, value in immutable.items() if value is not None and current.get(key) != value}
        if drift:
            module.fail_json(msg="DLC VPC connection identity is immutable", immutable_drift=drift)
        module.exit_json(changed=False, connection=current, endpoint_id=current.get("UserVpcEndpointId"))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
