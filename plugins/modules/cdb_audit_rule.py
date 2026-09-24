#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdb_audit_rule
short_description: Create or delete a Tencent Cloud CDB audit rule
version_added: "1.1.0"
description:
  - Creates or deletes a Tencent Cloud CDB (MySQL) audit rule, identified by its
    rule name. The module is idempotent; it reads the current audit rules before
    changing anything.
  - The CDB SDK exposes the audit-rule filter payload as nested SDK models
    (C{Account/Host/SqlType/...} groups), each wrapping a list of per-field
    filters. The module accepts the same nested shape under I(rule_filters) so
    the request can be built verbatim.
options:
  state:
    description: Desired state of the audit rule.
    type: str
    choices: [present, absent]
    default: present
  rule_name:
    description: Unique name of the audit rule.
    type: str
    required: true
  description:
    description: Human-readable description of the audit rule.
    type: str
  audit_all:
    description: Whether to audit all (override the per-field filters).
    type: bool
    default: false
  rule_filters:
    description:
      - Nested audit-rule filter payload, mirroring the CDB SDK
        C(AuditRuleFilters) shape. A list of groups, each group being a mapping
        with a C(rule_filters) key holding the per-field filters
        (C(type), C(value) as a list, C(compare)).
      - Required when I(state=present).
    type: list
    elements: dict
    required: true
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a CDB audit rule
  susunola.tencentcloud.cdb_audit_rule:
    rule_name: rule-host-prod
    description: Audit all access from the prod host
    rule_filters:
      - rule_filters:
          - type: host
            value:
              - "10.0.0.%"
            compare: "="

- name: Delete a CDB audit rule
  susunola.tencentcloud.cdb_audit_rule:
    rule_name: rule-host-prod
    state: absent
'''

RETURN = r'''
rule_name:
  description: Name of the audit rule the operation targeted.
  returned: always
  type: str
rule_id:
  description: Rule ID of the audit rule after the operation (empty when absent).
  returned: always
  type: str
exists:
  description: Whether the audit rule exists after the operation.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load():
    from tencentcloud.cdb.v20170320 import cdb_client, models
    return models, cdb_client


def _build_rule_filters(models, raw):
    groups = []
    for group in (raw or []):
        inner = []
        for rf in group.get("rule_filters", []) or []:
            item = models.RuleFilters()
            item.Type = rf.get("type")
            item.Value = rf.get("value") or []
            item.Compare = rf.get("compare")
            inner.append(item)
        wrapper = models.AuditRuleFilters()
        wrapper.RuleFilters = inner
        groups.append(wrapper)
    return groups


def find_rule(module, client, models, rule_name):
    request = models.DescribeAuditRulesRequest()
    request.RuleName = rule_name
    response = module.sdk_call(client.DescribeAuditRules, request)
    items = list(getattr(response, "Items", None) or [])
    for item in items:
        if getattr(item, "RuleName", None) == rule_name:
            return item
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "rule_name": {"type": "str", "required": True},
            "description": {"type": "str"},
            "audit_all": {"type": "bool", "default": False},
            "rule_filters": {"type": "list", "elements": "dict", "required": True},
        },
        required_if=[("state", "present", ("rule_filters",))],
        supports_check_mode=True,
    )
    p = module.params
    name = p["rule_name"]
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, cdb_client = _load()
    client = module.create_client(cdb_client.CdbClient, "cdb.tencentcloudapi.com")
    try:
        current = find_rule(module, client, models, name)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                rule_name=name,
                rule_id=getattr(current, "RuleId", "") if current else "",
                exists=bool(current),
                msg="Audit rule %s already %s" % (name, "present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                rule_name=name,
                rule_id="" if desired_present else (getattr(current, "RuleId", "") if current else ""),
                exists=desired_present,
                msg="Would %s audit rule %s" % ("create" if desired_present else "delete", name),
            )
        if desired_present:
            request = models.CreateAuditRuleRequest()
            request.RuleName = name
            request.RuleFilters = _build_rule_filters(models, p["rule_filters"])
            request.AuditAll = p["audit_all"]
            if p["description"] is not None:
                request.Description = p["description"]
            module.sdk_call(client.CreateAuditRule, request)
            final = find_rule(module, client, models, name)
            module.exit_json(
                changed=True,
                rule_name=name,
                rule_id=getattr(final, "RuleId", "") if final else "",
                exists=bool(final),
                msg="Created audit rule %s" % name,
            )
        else:
            request = models.DeleteAuditRuleRequest()
            request.RuleId = getattr(current, "RuleId", "")
            module.sdk_call(client.DeleteAuditRule, request)
            module.exit_json(
                changed=True,
                rule_name=name,
                rule_id="",
                exists=False,
                msg="Deleted audit rule %s" % name,
            )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud CDB audit rule request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
