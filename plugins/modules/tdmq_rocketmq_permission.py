#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: tdmq_rocketmq_permission
short_description: Manage TDMQ RocketMQ namespace role permissions
version_added: "0.14.0"
description: Grants an exact set of produce and consume permissions to a RocketMQ role in a namespace.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, required: true, description: RocketMQ cluster ID.}
  namespace: {type: str, required: true, description: RocketMQ namespace.}
  role_name: {type: str, required: true, description: RocketMQ role name.}
  permissions: {type: list, elements: str, choices: [produce, consume], default: [produce, consume], description: Exact namespace permission set.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdmq_rocketmq_permission:
    cluster_id: rocketmq-xxxxxxxx
    namespace: production
    role_name: order-service
    permissions: [produce, consume]
'''
RETURN = r'''permission: {description: RocketMQ namespace role permission metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client
    return models, tdmq_client


def describe_request(models, p, offset=0):
    request = models.DescribeRocketMQEnvironmentRolesRequest()
    request.ClusterId, request.EnvironmentId, request.Offset, request.Limit, request.RoleName = p["cluster_id"], p["namespace"], offset, 20, p["role_name"]
    return request


def create_request(models, p):
    request = models.CreateRocketMQEnvironmentRoleRequest()
    request.EnvironmentId, request.RoleName, request.Permissions, request.ClusterId = p["namespace"], p["role_name"], sorted(set(p["permissions"])), p["cluster_id"]
    return request


def update_request(models, p):
    request = models.ModifyRocketMQEnvironmentRoleRequest()
    request.EnvironmentId, request.RoleName, request.Permissions, request.ClusterId = p["namespace"], p["role_name"], sorted(set(p["permissions"])), p["cluster_id"]
    return request


def delete_request(models, p):
    request = models.DeleteRocketMQEnvironmentRolesRequest()
    request.EnvironmentId, request.RoleNames, request.ClusterId = p["namespace"], [p["role_name"]], p["cluster_id"]
    return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeRocketMQEnvironmentRoles, describe_request(models, p, offset)); items = list(response.EnvironmentRoleSets or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("RoleName") == p["role_name"] and value.get("EnvironmentId") == p["namespace"]: return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0): return None


def comparable(value):
    return {"EnvironmentId": value.get("EnvironmentId"), "RoleName": value.get("RoleName"), "Permissions": sorted(set(value.get("Permissions") or []))}


def desired(p):
    return {"EnvironmentId": p["namespace"], "RoleName": p["role_name"], "Permissions": sorted(set(p["permissions"]))}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "cluster_id": {"required": True}, "namespace": {"required": True}, "role_name": {"required": True}, "permissions": {"type": "list", "elements": "str", "choices": ["produce", "consume"], "default": ["produce", "consume"]}}, supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, permission=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteRocketMQEnvironmentRoles, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), permission=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target: module.exit_json(changed=False, permission=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            method = client.ModifyRocketMQEnvironmentRole if current else client.CreateRocketMQEnvironmentRole
            module.sdk_call(method, update_request(models, p) if current else create_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), permission=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
