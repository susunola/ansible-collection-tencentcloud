#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tcr_replication_rule
short_description: Manage Tencent Cloud TCR replication rules
version_added: "0.14.0"
description: Creates, updates, enables and deletes Enterprise Edition TCR replication policies.
options:
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  registry_id: {description: Source registry ID., type: str, required: true}
  destination_registry_id: {description: Destination replication registry ID., type: str, required: true}
  destination_region_id: {description: Destination region numeric ID., type: int, required: true}
  name: {description: Replication rule name., type: str, required: true}
  destination_namespace: {description: Destination namespace template., type: str, default: ''}
  filters:
    description: Replication filters.
    type: list
    elements: dict
    default: []
    suboptions:
      type: {description: Filter type., type: str, required: true}
      value: {description: Filter value., type: str, required: true}
  override: {description: Overwrite an existing destination image., type: bool, default: true}
  deletion: {description: Replicate source image deletion., type: bool, default: false}
  enabled: {description: Enable the replication rule., type: bool, default: true}
  description: {description: Rule description., type: str, default: ''}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tcr_replication_rule:
    registry_id: tcr-xxxxxxxx
    destination_registry_id: tcr-yyyyyyyy
    destination_region_id: 4
    name: production-images
    filters:
      - {type: namespace, value: production}
"""
RETURN = r"""replication_rule: {description: Replication rule metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tcr.v20190924 import models, tcr_client

    return models, tcr_client


def filter_models(models, values):
    result = []
    for value in values:
        item = models.ReplicationFilter()
        item.Type, item.Value = value["type"], value["value"]
        result.append(item)
    return result


def desired(p):
    return {
        "Name": p["name"],
        "Description": p["description"],
        "Override": p["override"],
        "Enabled": p["enabled"],
        "Filters": sorted(p["filters"], key=lambda x: (x["type"], x["value"])),
    }


def normalize(value):
    filters = [{"type": x.get("Type"), "value": x.get("Value")} for x in (value.get("Filters") or [])]
    return {
        "Name": value.get("Name"),
        "Description": value.get("Description") or "",
        "Override": bool(value.get("Override")),
        "Enabled": bool(value.get("Enabled")),
        "Filters": sorted(filters, key=lambda x: (x["type"], x["value"])),
    }


def find(module, client, models, registry_id, name):
    page = 1
    while True:
        request = models.DescribeReplicationPoliciesRequest()
        request.RegistryId, request.Page, request.PageSize = registry_id, page, 100
        response = module.sdk_call(client.DescribeReplicationPolicies, request)
        items = list(response.ReplicationPolicyInfoList or [])
        matches = [x._serialize(allow_none=True) for x in items if x.Name == name]
        if matches:
            return matches[0]
        if len(items) < 100 or page * 100 >= int(response.TotalCount or 0):
            return None
        page += 1


def rule_model(models, p, modifying=False):
    rule = models.ModifyReplicationRule() if modifying else models.ReplicationRule()
    if not modifying:
        rule.Name = p["name"]
    rule.DestNamespace, rule.Override, rule.Deletion = p["destination_namespace"], p["override"], p["deletion"]
    rule.Filters = filter_models(models, p["filters"])
    if modifying:
        rule.Enabled = p["enabled"]
    return rule


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "registry_id": {"required": True},
            "destination_registry_id": {"required": True},
            "destination_region_id": {"type": "int", "required": True},
            "name": {"required": True},
            "destination_namespace": {"default": ""},
            "filters": {
                "type": "list",
                "elements": "dict",
                "default": [],
                "options": {"type": {"type": "str", "required": True}, "value": {"type": "str", "required": True}},
            },
            "override": {"type": "bool", "default": True},
            "deletion": {"type": "bool", "default": False},
            "enabled": {"type": "bool", "default": True},
            "description": {"default": ""},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TcrClient, "tcr.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["registry_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, replication_rule=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteReplicationRuleRequest()
                request.SourceRegistryId, request.RuleName, request.Description = p["registry_id"], p["name"], p["description"]
                module.sdk_call(client.DeleteReplicationRule, request)
            module.exit_json(changed=True, **(diff or {}), replication_rule=current if module.check_mode else None)
        wanted = desired(p)
        if current and normalize(current) == wanted:
            module.exit_json(changed=False, replication_rule=current)
        diff = maybe_diff(module, normalize(current) if current else None, wanted)
        if not module.check_mode:
            if current:
                request = models.ModifyReplicationRequest()
                request.SourceRegistryId, request.RuleName = p["registry_id"], p["name"]
                request.Rule, request.Description = rule_model(models, p, True), p["description"]
                module.sdk_call(client.ModifyReplication, request)
            else:
                request = models.ManageReplicationRequest()
                request.SourceRegistryId, request.DestinationRegistryId = p["registry_id"], p["destination_registry_id"]
                request.DestinationRegionId, request.Description = p["destination_region_id"], p["description"]
                request.Rule = rule_model(models, p)
                module.sdk_call(client.ManageReplication, request)
                if not p["enabled"]:
                    update = models.ModifyReplicationRequest()
                    update.SourceRegistryId, update.RuleName = p["registry_id"], p["name"]
                    update.Rule, update.Description = rule_model(models, p, True), p["description"]
                    module.sdk_call(client.ModifyReplication, update)
            current = find(module, client, models, p["registry_id"], p["name"])
        module.exit_json(changed=True, **(diff or {}), replication_rule=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
