#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_governance_service
short_description: Manage a Tencent Cloud TSE governance service
version_added: "0.14.0"
description: Creates, updates and deletes a governance service with exact operator and visibility sets.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
  namespace: {type: str, required: true, description: Governance namespace name.}
  name: {type: str, required: true, description: Service name.}
  comment: {type: str, description: Service description.}
  department: {type: str, description: Owning department.}
  business: {type: str, description: Owning business.}
  metadata: {type: list, elements: dict, description: SDK service metadata entries.}
  user_ids: {type: list, elements: str, description: Exact operator user IDs.}
  group_ids: {type: list, elements: str, description: Exact operator group IDs.}
  export_to: {type: list, elements: str, description: Exact namespaces allowed to discover the service.}
  sync_to_global_registry: {type: bool, description: Synchronize to the global registry.}
  service_type: {type: int, choices: [0, 1, 2], default: 0, description: Microservice, MCP Server or AI Agent type.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_governance_service:
    instance_id: ins-xxxxxxxx
    namespace: production
    name: orders
    export_to: [shared]
"""
RETURN = r"""service: {description: Effective governance service metadata., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def describe_request(models, p):
    r = models.DescribeGovernanceServicesRequest()
    r.InstanceId, r.Namespace, r.Name, r.Offset, r.Limit = p["instance_id"], p["namespace"], p["name"], 0, 100
    return r


def _model(models, value):
    x = models.GovernanceServiceInput()
    x.from_json_string(json.dumps(value))
    return x


def request(cls, models, p, value):
    r = cls()
    r.InstanceId = p["instance_id"]
    r.GovernanceServices = [_model(models, value)]
    return r


def find(module, client, models, p):
    values = module.sdk_call(client.DescribeGovernanceServices, describe_request(models, p)).Content or []
    matches = [x._serialize(allow_none=True) for x in values if x.Name == p["name"] and x.Namespace == p["namespace"]]
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE governance services matched", name=p["name"], namespace=p["namespace"])
    return matches[0] if matches else None


def desired(p):
    mapping = {
        "comment": "Comment",
        "department": "Department",
        "business": "Business",
        "metadata": "Metadatas",
        "user_ids": "UserIds",
        "group_ids": "GroupIds",
        "export_to": "ExportTo",
        "sync_to_global_registry": "SyncToGlobalRegistry",
        "service_type": "Type",
    }
    value = {"Name": p["name"], "Namespace": p["namespace"]}
    for source, target in mapping.items():
        if p.get(source) is not None:
            value[target] = sorted(p[source]) if source in ("user_ids", "group_ids", "export_to") else p[source]
    return value


def comparable(value, target):
    result = {key: value.get(key) for key in target}
    for key in ("UserIds", "GroupIds", "ExportTo"):
        if key in result:
            result[key] = sorted(result[key] or [])
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
            "namespace": {"required": True},
            "name": {"required": True},
            "comment": {},
            "department": {},
            "business": {},
            "metadata": {"type": "list", "elements": "dict"},
            "user_ids": {"type": "list", "elements": "str"},
            "group_ids": {"type": "list", "elements": "str"},
            "export_to": {"type": "list", "elements": "str"},
            "sync_to_global_registry": {"type": "bool"},
            "service_type": {"type": "int", "choices": [0, 1, 2], "default": 0},
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
                module.exit_json(changed=False, service=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(
                    client.DeleteGovernanceServices,
                    request(models.DeleteGovernanceServicesRequest, models, p, {"Name": p["name"], "Namespace": p["namespace"]}),
                )
            module.exit_json(changed=True, **(diff or {}), service=None)
        target = desired(p)
        if current and comparable(current, target) == target:
            module.exit_json(changed=False, service=current)
        diff = maybe_diff(module, comparable(current or {}, target) if current else None, target)
        if not module.check_mode:
            payload = mutation(current, target)
            api = client.ModifyGovernanceServices if current else client.CreateGovernanceServices
            cls = models.ModifyGovernanceServicesRequest if current else models.CreateGovernanceServicesRequest
            module.sdk_call(api, request(cls, models, p, payload))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), service=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
