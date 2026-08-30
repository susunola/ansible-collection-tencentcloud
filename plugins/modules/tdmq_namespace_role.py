#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: tdmq_namespace_role
short_description: Manage TDMQ Pulsar namespace role permissions
version_added: "0.14.0"
description: Creates, updates and deletes role permission bindings in a Pulsar namespace.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, required: true, description: Pulsar cluster ID.}
  namespace: {type: str, required: true, description: Pulsar namespace name.}
  role_name: {type: str, required: true, description: TDMQ role name.}
  permissions: {type: list, elements: str, choices: [produce, consume], default: [produce, consume], description: Complete desired permission set.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdmq_namespace_role:
    cluster_id: pulsar-xxxxxxxx
    namespace: production
    role_name: application
    permissions: [produce, consume]
'''
RETURN = r'''namespace_role: {description: TDMQ namespace role binding metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client
    return models, tdmq_client


def describe_request(models, p, offset=0):
    request = models.DescribeEnvironmentRolesRequest(); request.ClusterId, request.EnvironmentId, request.RoleName = p["cluster_id"], p["namespace"], p["role_name"]
    request.Offset, request.Limit = offset, 20; return request


def apply_request(request, p):
    request.ClusterId, request.EnvironmentId, request.RoleName = p["cluster_id"], p["namespace"], p["role_name"]
    request.Permissions = sorted(set(p["permissions"])); return request


def create_request(models, p): return apply_request(models.CreateEnvironmentRoleRequest(), p)
def update_request(models, p): return apply_request(models.ModifyEnvironmentRoleRequest(), p)


def delete_request(models, p):
    request = models.DeleteEnvironmentRolesRequest(); request.ClusterId, request.EnvironmentId, request.RoleNames = p["cluster_id"], p["namespace"], [p["role_name"]]; return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeEnvironmentRoles, describe_request(models, p, offset)); items = list(response.EnvironmentRoleSets or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("RoleName") == p["role_name"]: return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0): return None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "cluster_id": {"required": True}, "namespace": {"required": True}, "role_name": {"required": True}, "permissions": {"type": "list", "elements": "str", "choices": ["produce", "consume"], "default": ["produce", "consume"]}}, supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, namespace_role=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteEnvironmentRoles, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), namespace_role=current if module.check_mode else None)
        target = sorted(set(p["permissions"])); before = sorted(set(current.get("Permissions") or [])) if current else None
        if before == target: module.exit_json(changed=False, namespace_role=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyEnvironmentRole if current else client.CreateEnvironmentRole, update_request(models, p) if current else create_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), namespace_role=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
