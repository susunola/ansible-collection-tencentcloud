#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: ckafka_acl_rule
short_description: Manage Tencent Cloud CKafka ACL rules
version_added: "0.14.0"
description: Creates and deletes prefixed or preset Topic ACL rules and updates whether preset rules apply to newly created topics.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: CKafka instance ID.}
  name: {type: str, required: true, description: ACL rule name.}
  pattern_type: {type: str, choices: [PREFIXED, PRESET], default: PREFIXED, description: Prefix matching or preset policy.}
  pattern: {type: str, description: Topic prefix required for C(PREFIXED) rules.}
  apply_to_new_topics: {type: bool, default: false, description: Apply a preset rule to newly created topics.}
  comment: {type: str, default: '', description: Immutable ACL rule comment.}
  rules:
    type: list
    elements: dict
    description: Immutable ACL entries contained by the rule. Required when C(state=present).
    suboptions:
      operation: {type: str, choices: [All, Read, Write], required: true, description: Allowed Kafka operation.}
      permission: {type: str, choices: [Allow, Deny], required: true, description: Allow or deny decision.}
      host: {type: str, default: '*', description: Client host pattern.}
      principal: {type: str, required: true, description: Principal such as C(User:producer).}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ckafka_acl_rule:
    instance_id: ckafka-xxxxxxxx
    name: orders-producers
    pattern_type: PREFIXED
    pattern: orders-
    rules:
      - operation: Write
        permission: Allow
        principal: User:producer
"""
RETURN = r"""acl_rule: {description: CKafka ACL rule metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.ckafka.v20190819 import ckafka_client, models

    return models, ckafka_client


def describe_request(models, p):
    request = models.DescribeAclRuleRequest()
    request.InstanceId, request.RuleName, request.PatternType = p["instance_id"], p["name"], p["pattern_type"]
    return request


def acl_entries(models, values):
    result = []
    for value in values:
        item = models.AclRuleInfo()
        item.Operation, item.PermissionType = value["operation"], value["permission"]
        item.Host, item.Principal = value["host"], value["principal"]
        result.append(item)
    return result


def create_request(models, p):
    request = models.CreateAclRuleRequest()
    request.InstanceId, request.ResourceType, request.PatternType, request.RuleName = p["instance_id"], "Topic", p["pattern_type"], p["name"]
    request.RuleList, request.Pattern = acl_entries(models, p["rules"]), p.get("pattern")
    request.IsApplied, request.Comment = int(p["apply_to_new_topics"]), p["comment"]
    return request


def update_request(models, p):
    request = models.ModifyAclRuleRequest()
    request.InstanceId, request.RuleName, request.IsApplied = p["instance_id"], p["name"], int(p["apply_to_new_topics"])
    return request


def delete_request(models, p):
    request = models.DeleteAclRuleRequest()
    request.InstanceId, request.RuleName = p["instance_id"], p["name"]
    return request


def normalized_rules(values):
    result = []
    for value in values or []:
        if hasattr(value, "_serialize"):
            value = value._serialize(allow_none=True)
        result.append(
            {
                "operation": value.get("Operation"),
                "permission": value.get("PermissionType"),
                "host": value.get("Host") or "*",
                "principal": value.get("Principal"),
            }
        )
    return sorted(result, key=lambda x: (x["principal"], x["host"], x["operation"], x["permission"]))


def comparable(value):
    return {
        "PatternType": value.get("PatternType"),
        "Pattern": value.get("Pattern"),
        "Comment": value.get("Comment") or "",
        "AclList": normalized_rules(value.get("AclList")),
        "IsApplied": int(value.get("IsApplied") or 0),
    }


def desired(p):
    return {
        "PatternType": p["pattern_type"],
        "Pattern": p.get("pattern"),
        "Comment": p["comment"],
        "AclList": normalized_rules(
            [{"Operation": x["operation"], "PermissionType": x["permission"], "Host": x["host"], "Principal": x["principal"]} for x in p["rules"]]
        ),
        "IsApplied": int(p["apply_to_new_topics"]),
    }


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeAclRule, describe_request(models, p))
    for item in list(response.Result.AclRuleList or []):
        value = item._serialize(allow_none=True)
        if value.get("RuleName") == p["name"]:
            return value
    return None


def run_module():
    rule = {
        "type": "list",
        "elements": "dict",
        "options": {
            "operation": {"choices": ["All", "Read", "Write"], "required": True},
            "permission": {"choices": ["Allow", "Deny"], "required": True},
            "host": {"default": "*"},
            "principal": {"required": True},
        },
    }
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "name": {"required": True},
            "pattern_type": {"choices": ["PREFIXED", "PRESET"], "default": "PREFIXED"},
            "pattern": {},
            "apply_to_new_topics": {"type": "bool", "default": False},
            "comment": {"default": ""},
            "rules": rule,
        },
        required_if=[("state", "present", ("rules",))],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and p["pattern_type"] == "PREFIXED" and not p["pattern"]:
        module.fail_json(msg="pattern is required for PREFIXED ACL rules")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CkafkaClient, "ckafka.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, acl_rule=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteAclRule, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), acl_rule=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, acl_rule=current)
        diff = maybe_diff(module, before, target)
        if current:
            require_immutable_unchanged(module, before, target, ("PatternType", "Pattern", "Comment", "AclList"), "CKafka ACL rule")
        if not module.check_mode:
            module.sdk_call(client.ModifyAclRule if current else client.CreateAclRule, update_request(models, p) if current else create_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), acl_rule=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
