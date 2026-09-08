#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_consumer
short_description: Manage a Tencent Cloud TSE API gateway consumer
version_added: "0.14.0"
description: Creates, updates and deletes an instance-unique API gateway consumer.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  consumer_id: {type: str, description: Existing consumer ID.}
  name: {type: str, description: Instance-unique consumer name.}
  priority: {type: str, choices: [Low, Medium, High], description: Consumer priority; creation defaults to Medium.}
  description: {type: str, description: Consumer description.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_consumer:
    gateway_id: gateway-xxxxxxxx
    name: mobile-application
    priority: High
"""
RETURN = r"""consumer: {description: Effective gateway consumer metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def list_request(models, p, offset=0):
    r = models.DescribeCloudNativeAPIGatewayConsumerListRequest()
    r.GatewayId, r.Offset, r.Limit = p["gateway_id"], offset, 20
    return r


def detail_request(models, p, consumer_id):
    r = models.DescribeCloudNativeAPIGatewayConsumerRequest()
    r.GatewayId, r.ConsumerId = p["gateway_id"], consumer_id
    return r


def create_request(models, p):
    r = models.CreateCloudNativeAPIGatewayConsumerRequest()
    r.GatewayId, r.Name, r.Priority, r.Description = p["gateway_id"], p["name"], p.get("priority") or "Medium", p.get("description")
    return r


def update_request(models, p, current):
    r = models.ModifyCloudNativeAPIGatewayConsumerRequest()
    r.GatewayId, r.ConsumerId, r.Name, r.Priority, r.Description = p["gateway_id"], current["ConsumerId"], p["name"], p["priority"], p.get("description")
    return r


def delete_request(models, p, current):
    r = models.DeleteCloudNativeAPIGatewayConsumerRequest()
    r.GatewayId, r.ConsumerId = p["gateway_id"], current["ConsumerId"]
    return r


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        result = module.sdk_call(client.DescribeCloudNativeAPIGatewayConsumerList, list_request(models, p, offset)).Result
        values = result.Consumers if result else []
        for item in values or []:
            value = item._serialize(allow_none=True)
            if (p.get("consumer_id") and value.get("ConsumerId") == p["consumer_id"]) or (not p.get("consumer_id") and value.get("Name") == p["name"]):
                matches.append(value)
        offset += len(values or [])
        if not result or offset >= int(result.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE gateway consumers matched; specify consumer_id")
    if not matches:
        return None
    detail = module.sdk_call(client.DescribeCloudNativeAPIGatewayConsumer, detail_request(models, p, matches[0]["ConsumerId"])).Result
    return detail._serialize(allow_none=True) if detail else matches[0]


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "gateway_id": {"required": True},
            "consumer_id": {},
            "name": {},
            "priority": {"choices": ["Low", "Medium", "High"]},
            "description": {},
        },
        required_one_of=[("consumer_id", "name")],
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
                module.exit_json(changed=False, consumer=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCloudNativeAPIGatewayConsumer, delete_request(models, p, current))
            module.exit_json(changed=True, **(diff or {}), consumer=None)
        if not current and not p.get("name"):
            module.fail_json(msg="name is required for a new TSE gateway consumer")
        target = {
            "Name": p.get("name") or current.get("Name"),
            "Priority": p.get("priority") or ((current or {}).get("Priority") if current else "Medium"),
            "Description": p.get("description") if p.get("description") is not None else (current or {}).get("Description"),
        }
        before = {key: (current or {}).get(key) for key in target}
        if current and before == target:
            module.exit_json(changed=False, consumer=current)
        diff = maybe_diff(module, before if current else None, target)
        if not module.check_mode:
            p["name"], p["priority"], p["description"] = target["Name"], target["Priority"], target["Description"]
            if current:
                module.sdk_call(client.ModifyCloudNativeAPIGatewayConsumer, update_request(models, p, current))
            else:
                response = module.sdk_call(client.CreateCloudNativeAPIGatewayConsumer, create_request(models, p))
                p["consumer_id"] = response.Result.ID
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), consumer=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
