#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_server_group
short_description: Manage a Tencent Cloud TSE gateway server group
version_added: "0.14.0"
description: Creates, resizes, updates and deletes a non-default cloud-native API gateway server group.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  group_id: {type: str, description: Existing group ID.}
  name: {type: str, description: Group name.}
  node_config: {type: dict, description: SDK CloudNativeAPIGatewayNodeConfig payload.}
  subnet_id: {type: str, description: Subnet ID used at creation.}
  description: {type: str, description: Group description.}
  internet_max_bandwidth_out: {type: int, description: Public bandwidth used at creation.}
  internet_config: {type: dict, description: SDK InternetConfig payload used at creation.}
  waiter_delay: {type: int, default: 5, description: Reconciliation polling interval.}
  waiter_timeout: {type: int, default: 600, description: Reconciliation timeout.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_server_group:
    gateway_id: gateway-xxxxxxxx
    name: production-secondary
    node_config: {Specification: 4c8g, Number: 3}
    subnet_id: subnet-xxxxxxxx
"""
RETURN = r"""
group: {description: Effective server group metadata., type: dict, returned: always}
task_id: {description: Latest asynchronous task ID., type: str, returned: when supplied by Tencent Cloud}
"""
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def list_request(models, p):
    r = models.DescribeNativeGatewayServerGroupsRequest()
    r.GatewayId, r.Offset, r.Limit = p["gateway_id"], 0, 100
    f = models.Filter()
    f.Name, f.Values = ("GroupId", [p["group_id"]]) if p.get("group_id") else ("Name", [p["name"]])
    r.Filters = [f]
    return r


def write_request(cls, p, payload):
    r = cls()
    r.from_json_string(json.dumps(payload))
    return r


def create_request(models, p):
    payload = {
        "GatewayId": p["gateway_id"],
        "Name": p["name"],
        "NodeConfig": p["node_config"],
        "SubnetId": p["subnet_id"],
        "Description": p.get("description"),
        "InternetMaxBandwidthOut": p.get("internet_max_bandwidth_out"),
        "InternetConfig": p.get("internet_config"),
    }
    return write_request(models.CreateNativeGatewayServerGroupRequest, p, {k: v for k, v in payload.items() if v is not None})


def update_request(models, p, group_id, target):
    return write_request(models.ModifyNativeGatewayServerGroupRequest, p, {"GatewayId": p["gateway_id"], "GroupId": group_id, **target})


def resize_request(models, p, group_id):
    return write_request(models.UpdateCloudNativeAPIGatewaySpecRequest, p, {"GatewayId": p["gateway_id"], "GroupId": group_id, "NodeConfig": p["node_config"]})


def delete_request(models, p, group_id):
    return write_request(models.DeleteNativeGatewayServerGroupRequest, p, {"GatewayId": p["gateway_id"], "GroupId": group_id})


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    return actual == expected


def find(module, client, models, p):
    result = module.sdk_call(client.DescribeNativeGatewayServerGroups, list_request(models, p)).Result
    values = result.GatewayGroupList if result else []
    matches = []
    for item in values or []:
        value = item._serialize(allow_none=True)
        if (p.get("group_id") and value.get("GroupId") == p["group_id"]) or (not p.get("group_id") and value.get("Name") == p.get("name")):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE gateway server groups matched; specify group_id")
    return matches[0] if matches else None


def wait(module, client, models, p, group_id, expected=None, absent=False):
    deadline = time.time() + p["waiter_timeout"]
    lookup = dict(p, group_id=group_id)
    while True:
        value = find(module, client, models, lookup)
        if absent and value is None:
            return None
        status = str((value or {}).get("Status") or "").lower()
        if not absent and status in ("running", "run", "success") and (expected is None or contains(value, expected)):
            return value
        if status in ("failed", "create_failed", "update_failed", "delete_failed"):
            module.fail_json(msg="TSE gateway server group operation failed", group=value)
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TSE gateway server group convergence", group=value)
        time.sleep(p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "gateway_id": {"required": True},
        "group_id": {},
        "name": {},
        "node_config": {"type": "dict"},
        "subnet_id": {},
        "description": {},
        "internet_max_bandwidth_out": {"type": "int"},
        "internet_config": {"type": "dict"},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 600},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("group_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, group=None)
            if current.get("IsFirstGroup") == 1:
                module.fail_json(msg="The default TSE gateway server group cannot be deleted", group_id=current["GroupId"])
            diff = maybe_diff(module, current, None)
            task_id = None
            if not module.check_mode:
                response = module.sdk_call(client.DeleteNativeGatewayServerGroup, delete_request(models, p, current["GroupId"]))
                task_id = getattr(getattr(response, "Result", None), "TaskId", None)
                wait(module, client, models, p, current["GroupId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), group=None, task_id=task_id)
        if not current:
            missing = [key for key in ("name", "node_config", "subnet_id") if p.get(key) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a TSE gateway server group", missing=missing)
            target = {"Name": p["name"], "NodeConfig": p["node_config"], "SubnetIds": p["subnet_id"], "Description": p.get("description")}
            diff = maybe_diff(module, None, target)
            task_id = None
            if not module.check_mode:
                response = module.sdk_call(client.CreateNativeGatewayServerGroup, create_request(models, p))
                result = response.Result
                group_id = result.GroupId
                task_id = getattr(result, "TaskId", None)
                current = wait(module, client, models, p, group_id, target)
            module.exit_json(changed=True, **(diff or {}), group=current if not module.check_mode else target, task_id=task_id)
        immutable = {"SubnetIds": p.get("subnet_id"), "InternetMaxBandwidthOut": p.get("internet_max_bandwidth_out")}
        immutable = {k: v for k, v in immutable.items() if v is not None}
        drift = {k: (current.get(k), v) for k, v in immutable.items() if not contains(current.get(k), v)}
        if drift:
            module.fail_json(msg="TSE gateway server group network placement is immutable", immutable_drift=drift)
        before = {"Name": current.get("Name"), "Description": current.get("Description"), "NodeConfig": current.get("NodeConfig")}
        target = dict(before)
        if p.get("name") is not None:
            target["Name"] = p["name"]
        if p.get("description") is not None:
            target["Description"] = p["description"]
        if p.get("node_config") is not None:
            target["NodeConfig"] = p["node_config"]
        metadata_changed = before["Name"] != target["Name"] or before["Description"] != target["Description"]
        node_changed = not contains(before["NodeConfig"], target["NodeConfig"])
        if not metadata_changed and not node_changed:
            module.exit_json(changed=False, group=current)
        diff = maybe_diff(module, before, target)
        task_id = None
        if not module.check_mode:
            if metadata_changed:
                module.sdk_call(
                    client.ModifyNativeGatewayServerGroup,
                    update_request(models, p, current["GroupId"], {"Name": target["Name"], "Description": target["Description"]}),
                )
            if node_changed:
                response = module.sdk_call(client.UpdateCloudNativeAPIGatewaySpec, resize_request(models, p, current["GroupId"]))
                task_id = getattr(getattr(response, "Result", None), "TaskId", None)
            current = wait(module, client, models, p, current["GroupId"], target)
        module.exit_json(changed=True, **(diff or {}), group=current if not module.check_mode else target, task_id=task_id)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
