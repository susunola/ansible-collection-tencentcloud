#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_consumer_group
short_description: Manage a Tencent Cloud TSE API gateway consumer group
version_added: "0.14.0"
description: Creates, updates and deletes an instance-unique API gateway consumer group.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  consumer_group_id: {type: str, description: Existing consumer group ID.}
  name: {type: str, description: Instance-unique consumer group name.}
  status: {type: str, choices: [Enable, Disable], description: Group status; creation defaults to Enable.}
  description: {type: str, description: Consumer group description.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_consumer_group:
    gateway_id: gateway-xxxxxxxx
    name: trusted-clients
    status: Enable
"""
RETURN = r"""consumer_group: {description: Effective consumer group metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def list_request(models, p, offset=0):
    r = models.DescribeCloudNativeAPIGatewayConsumerGroupListRequest()
    r.GatewayId, r.Offset, r.Limit = p["gateway_id"], offset, 20
    return r


def detail_request(models, p, group_id):
    r = models.DescribeCloudNativeAPIGatewayConsumerGroupRequest()
    r.GatewayId, r.ConsumerGroupId = p["gateway_id"], group_id
    return r


def create_request(models, p):
    r = models.CreateCloudNativeAPIGatewayConsumerGroupRequest()
    r.GatewayId, r.Name, r.Status, r.Description = p["gateway_id"], p["name"], p["status"], p.get("description")
    return r


def update_request(models, p, current):
    r = models.ModifyCloudNativeAPIGatewayConsumerGroupRequest()
    r.GatewayId, r.ConsumerGroupId, r.Name, r.Status, r.Description = p["gateway_id"], current["ConsumerGroupId"], p["name"], p["status"], p.get("description")
    return r


def delete_request(models, p, current):
    r = models.DeleteCloudNativeAPIGatewayConsumerGroupRequest()
    r.GatewayId, r.ConsumerGroupId = p["gateway_id"], current["ConsumerGroupId"]
    return r


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        result = module.sdk_call(client.DescribeCloudNativeAPIGatewayConsumerGroupList, list_request(models, p, offset)).Result
        values = result.ConsumerGroups if result else []
        for item in values or []:
            value = item._serialize(allow_none=True)
            if (p.get("consumer_group_id") and value.get("ConsumerGroupId") == p["consumer_group_id"]) or (
                not p.get("consumer_group_id") and value.get("Name") == p["name"]
            ):
                matches.append(value)
        offset += len(values or [])
        if not result or offset >= int(result.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE gateway consumer groups matched; specify consumer_group_id")
    if not matches:
        return None
    detail = module.sdk_call(client.DescribeCloudNativeAPIGatewayConsumerGroup, detail_request(models, p, matches[0]["ConsumerGroupId"])).Result
    return detail._serialize(allow_none=True) if detail else matches[0]


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "gateway_id": {"required": True},
            "consumer_group_id": {},
            "name": {},
            "status": {"choices": ["Enable", "Disable"]},
            "description": {},
        },
        required_one_of=[("consumer_group_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, consumer_group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCloudNativeAPIGatewayConsumerGroup, delete_request(models, p, current))
            module.exit_json(changed=True, **(diff or {}), consumer_group=None)
        if not current and not p.get("name"):
            module.fail_json(msg="name is required for a new TSE gateway consumer group")
        target = {
            "Name": p.get("name") or current.get("Name"),
            "Status": p.get("status") or ((current or {}).get("Status") if current else "Enable"),
            "Description": p.get("description") if p.get("description") is not None else (current or {}).get("Description"),
        }
        before = {key: (current or {}).get(key) for key in target}
        if current and before == target:
            module.exit_json(changed=False, consumer_group=current)
        diff = maybe_diff(module, before if current else None, target)
        if not module.check_mode:
            p["name"], p["status"], p["description"] = target["Name"], target["Status"], target["Description"]
            if current:
                module.sdk_call(client.ModifyCloudNativeAPIGatewayConsumerGroup, update_request(models, p, current))
            else:
                response = module.sdk_call(client.CreateCloudNativeAPIGatewayConsumerGroup, create_request(models, p))
                p["consumer_group_id"] = response.Result.ID
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), consumer_group=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
