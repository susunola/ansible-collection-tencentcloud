#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: chdfs_access_rules
short_description: Reconcile Tencent Cloud CHDFS access rules
version_added: "0.14.0"
description: Reconciles the complete access-rule set of a CHDFS access group.
options:
  access_group_id: {type: str, required: true, description: Access group ID.}
  rules:
    type: list
    elements: dict
    required: true
    description: Exact desired rule set, matched by address.
    suboptions:
      address: {type: str, required: true, description: CIDR or IP address.}
      access_mode: {type: int, required: true, choices: [1, 2], description: Read-only or read-write mode.}
      priority: {type: int, required: true, description: Priority from 1 through 100.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.chdfs_access_rules:
    access_group_id: ag-xxxxxxxx
    rules:
      - {address: 10.0.0.0/16, access_mode: 2, priority: 10}
"""
RETURN = r"""rules: {description: Effective CHDFS access rules., type: list, elements: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.chdfs.v20201112 import models, chdfs_client

    return models, chdfs_client


def describe_request(models, access_group_id):
    r = models.DescribeAccessRulesRequest()
    r.AccessGroupId = access_group_id
    return r


def _model(models, value, rule_id=None):
    r = models.AccessRule()
    r.AccessRuleId = rule_id
    r.Address = value["address"]
    r.AccessMode = value["access_mode"]
    r.Priority = value["priority"]
    return r


def create_request(models, access_group_id, rules):
    r = models.CreateAccessRulesRequest()
    r.AccessGroupId = access_group_id
    r.AccessRules = [_model(models, x) for x in rules]
    return r


def update_request(models, rules):
    r = models.ModifyAccessRulesRequest()
    r.AccessRules = [_model(models, x, x["access_rule_id"]) for x in rules]
    return r


def delete_request(models, ids):
    r = models.DeleteAccessRulesRequest()
    r.AccessRuleIds = ids
    return r


def describe(module, client, models, access_group_id):
    return [x._serialize(allow_none=True) for x in (module.sdk_call(client.DescribeAccessRules, describe_request(models, access_group_id)).AccessRules or [])]


def normalized_current(values):
    return sorted(
        [{"address": x.get("Address"), "access_mode": x.get("AccessMode"), "priority": x.get("Priority")} for x in values], key=lambda x: x["address"]
    )


def normalized_desired(values):
    return sorted(values, key=lambda x: x["address"])


def run_module():
    rule = {
        "type": "dict",
        "options": {
            "address": {"required": True},
            "access_mode": {"type": "int", "required": True, "choices": [1, 2]},
            "priority": {"type": "int", "required": True},
        },
    }
    module = TencentCloudModule(
        argument_spec={"access_group_id": {"required": True}, "rules": {"type": "list", "elements": "dict", "required": True, "options": rule["options"]}},
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ChdfsClient, "chdfs.tencentcloudapi.com")
    try:
        addresses = [x["address"] for x in p["rules"]]
        if len(addresses) != len(set(addresses)):
            module.fail_json(msg="CHDFS access rule addresses must be unique")
        if len(addresses) > 10:
            module.fail_json(msg="CHDFS accepts at most 10 access rules per access group")
        invalid_priorities = [x["priority"] for x in p["rules"] if not 1 <= x["priority"] <= 100]
        if invalid_priorities:
            module.fail_json(msg="CHDFS access rule priority must be between 1 and 100", priorities=invalid_priorities)
        current = describe(module, client, models, p["access_group_id"])
        before = normalized_current(current)
        target = normalized_desired(p["rules"])
        if before == target:
            module.exit_json(changed=False, rules=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            existing = {x["Address"]: x for x in current}
            desired = {x["address"]: x for x in p["rules"]}
            removed = [x["AccessRuleId"] for a, x in existing.items() if a not in desired]
            created = [x for a, x in desired.items() if a not in existing]
            updated = []
            for address, value in desired.items():
                old = existing.get(address)
                if old and (old.get("AccessMode") != value["access_mode"] or old.get("Priority") != value["priority"]):
                    updated.append(dict(value, access_rule_id=old["AccessRuleId"]))
            if removed:
                module.sdk_call(client.DeleteAccessRules, delete_request(models, removed))
            if created:
                module.sdk_call(client.CreateAccessRules, create_request(models, p["access_group_id"], created))
            if updated:
                module.sdk_call(client.ModifyAccessRules, update_request(models, updated))
            current = describe(module, client, models, p["access_group_id"])
        module.exit_json(changed=True, **(diff or {}), rules=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
