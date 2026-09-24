#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_governance_namespace
short_description: Manage a Tencent Cloud TSE governance namespace
version_added: "0.14.0"
description: Creates, updates and deletes a governance namespace with exact operator and service visibility sets.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - TSE engine instance ID.
    type: str
    required: true
  name:
    description:
      - Namespace name.
    type: str
    required: true
  comment:
    description:
      - Namespace description.
    type: str
  user_ids:
    description:
      - Exact user IDs allowed to operate the namespace.
    type: list
    elements: str
  group_ids:
    description:
      - Exact group IDs allowed to operate the namespace.
    type: list
    elements: str
  service_export_to:
    description:
      - Exact namespaces allowed to discover its services.
    type: list
    elements: str
  sync_to_global_registry:
    description:
      - Synchronize to the global registry.
    type: bool

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
  idempotency:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_governance_namespace:
    instance_id: ins-xxxxxxxx
    name: production
    comment: Production services
    service_export_to: [shared]
"""
RETURN = r"""namespace: {description: Effective governance namespace metadata., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def describe_request(models, p):
    r = models.DescribeGovernanceNamespacesRequest()
    r.InstanceId, r.Name, r.Offset, r.Limit = p["instance_id"], p["name"], 0, 100
    return r


def _model(models, value):
    x = models.GovernanceNamespaceInput()
    x.from_json_string(json.dumps(value))
    return x


def request(cls, models, p, value):
    r = cls()
    r.InstanceId = p["instance_id"]
    r.GovernanceNamespaces = [_model(models, value)]
    return r


def find(module, client, models, p):
    values = module.sdk_call(client.DescribeGovernanceNamespaces, describe_request(models, p)).Content or []
    matches = [x._serialize(allow_none=True) for x in values if x.Name == p["name"]]
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE governance namespaces matched", name=p["name"])
    return matches[0] if matches else None


def desired(p):
    mapping = {
        "comment": "Comment",
        "user_ids": "UserIds",
        "group_ids": "GroupIds",
        "service_export_to": "ServiceExportTo",
        "sync_to_global_registry": "SyncToGlobalRegistry",
    }
    value = {"Name": p["name"]}
    for source, target in mapping.items():
        if p.get(source) is not None:
            value[target] = sorted(p[source]) if isinstance(p[source], list) else p[source]
    return value


def comparable(value, target):
    result = {"Name": value.get("Name")}
    for key in target:
        if key != "Name":
            result[key] = sorted(value.get(key) or []) if isinstance(target[key], list) else value.get(key)
    return result


def mutation(current, target):
    value = dict(target)
    for key, remove_key in (("UserIds", "RemoveUserIds"), ("GroupIds", "RemoveGroupIds")):
        if key in target:
            before = set((current or {}).get(key) or [])
            after = set(target[key])
            value[key] = sorted(after - before)
            value[remove_key] = sorted(before - after)
    return value


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "name": {"required": True},
            "comment": {},
            "user_ids": {"type": "list", "elements": "str"},
            "group_ids": {"type": "list", "elements": "str"},
            "service_export_to": {"type": "list", "elements": "str"},
            "sync_to_global_registry": {"type": "bool"},
        },
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
                module.exit_json(changed=False, namespace=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteGovernanceNamespaces, request(models.DeleteGovernanceNamespacesRequest, models, p, {"Name": p["name"]}))
            module.exit_json(changed=True, **(diff or {}), namespace=None)
        target = desired(p)
        if current and comparable(current, target) == target:
            module.exit_json(changed=False, namespace=current)
        diff = maybe_diff(module, comparable(current or {}, target) if current else None, target)
        if not module.check_mode:
            payload = mutation(current, target)
            api = client.ModifyGovernanceNamespaces if current else client.CreateGovernanceNamespaces
            cls = models.ModifyGovernanceNamespacesRequest if current else models.CreateGovernanceNamespacesRequest
            module.sdk_call(api, request(cls, models, p, payload))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), namespace=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
