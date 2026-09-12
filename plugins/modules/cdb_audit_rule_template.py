#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdb_audit_rule_template
short_description: Create or delete a Tencent Cloud CDB audit rule template
version_added: "1.1.0"
description:
  - Creates or deletes a Tencent Cloud CDB (MySQL) audit rule template,
    identified by its template name. The module is idempotent; it reads the
    current audit rule templates before changing anything and matches on the
    template name.
  - The CDB SDK exposes the audit-rule filter payload as a flat list of
    C(RuleFilters) objects (each with C(Type), C(Value) as a list, C(Compare)).
    The module accepts the same flat shape under I(rule_filters) so the request
    can be built verbatim.
options:
  state:
    description: Desired state of the audit rule template.
    type: str
    choices: [present, absent]
    default: present
  rule_template_name:
    description: Unique name of the audit rule template (max 30 characters).
    type: str
    required: true
  description:
    description: Human-readable description of the audit rule template (max 200 characters).
    type: str
  rule_filters:
    description:
      - Flat list of audit-rule filter objects, mirroring the CDB SDK
        C(RuleFilters) shape. Each item is a mapping with C(type), C(value) as
        a list of strings, and C(compare).
      - C(compare) is validated server-side and accepts only C(EXC), C(EQS),
        C(NEQ), C(REG) and C(INC); anything else is rejected with
        C(InvalidParameter.InvalidParameterError).
      - Required when I(state=present).
    type: list
    elements: dict
  alarm_level:
    description: Alarm level. 1 - low, 2 - medium, 3 - high. Default 1.
    type: int
    choices: [1, 2, 3]
  alarm_policy:
    description: Alarm policy. 0 - no alarm, 1 - alarm. Default 0.
    type: int
    choices: [0, 1]
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
- name: Create a CDB audit rule template that audits prod-host access
  susunola.tencentcloud.cdb_audit_rule_template:
    rule_template_name: tmpl-host-prod
    description: Audit all access from the prod host
    rule_filters:
      - type: host
        value:
          - "10.0.0.%"
        # compare accepts EXC / EQS / NEQ / REG / INC only.
        compare: INC
    alarm_level: 2
    alarm_policy: 1

- name: Delete a CDB audit rule template
  susunola.tencentcloud.cdb_audit_rule_template:
    rule_template_name: tmpl-host-prod
    state: absent
'''

RETURN = r'''
rule_template_name:
  description: Name of the audit rule template the operation targeted.
  returned: always
  type: str
rule_template_id:
  description: Template ID of the audit rule template after the operation (empty when absent).
  returned: always
  type: str
exists:
  description: Whether the audit rule template exists after the operation.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load():
    from tencentcloud.cdb.v20170320 import cdb_client, models
    return models, cdb_client


def _build_rule_filters(models, raw):
    items = []
    for rf in (raw or []):
        item = models.RuleFilters()
        item.Type = rf.get("type")
        item.Value = rf.get("value") or []
        item.Compare = rf.get("compare")
        items.append(item)
    return items


def find_template(module, client, models, name):
    request = models.DescribeAuditRuleTemplatesRequest()
    request.RuleTemplateNames = [name]
    request.Limit = 100
    request.Offset = 0
    response = module.sdk_call(client.DescribeAuditRuleTemplates, request)
    items = list(getattr(response, "Items", None) or [])
    for item in items:
        if getattr(item, "RuleTemplateName", None) == name:
            return item
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "rule_template_name": {"type": "str", "required": True},
            "description": {"type": "str"},
            "rule_filters": {"type": "list", "elements": "dict"},
            "alarm_level": {"type": "int", "choices": [1, 2, 3]},
            "alarm_policy": {"type": "int", "choices": [0, 1]},
        },
        required_if=[("state", "present", ("rule_filters",))],
        supports_check_mode=True,
    )
    p = module.params
    name = p["rule_template_name"]
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, cdb_client = _load()
    client = module.create_client(cdb_client.CdbClient, "cdb.tencentcloudapi.com")
    try:
        current = find_template(module, client, models, name)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                rule_template_name=name,
                rule_template_id=getattr(current, "RuleTemplateId", "") if current else "",
                exists=bool(current),
                msg="CDB audit rule template %s already %s" % (name, "present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                rule_template_name=name,
                rule_template_id="" if desired_present else (getattr(current, "RuleTemplateId", "") if current else ""),
                exists=desired_present,
                msg="Would %s CDB audit rule template %s" % ("create" if desired_present else "delete", name),
            )
        if desired_present:
            request = models.CreateAuditRuleTemplateRequest()
            request.RuleTemplateName = name
            request.RuleFilters = _build_rule_filters(models, p["rule_filters"])
            if p["description"] is not None:
                request.Description = p["description"]
            if p["alarm_level"] is not None:
                request.AlarmLevel = p["alarm_level"]
            if p["alarm_policy"] is not None:
                request.AlarmPolicy = p["alarm_policy"]
            response = module.sdk_call(client.CreateAuditRuleTemplate, request)
            created_id = getattr(response, "RuleTemplateId", None)
        else:
            request = models.DeleteAuditRuleTemplatesRequest()
            request.RuleTemplateIds = [getattr(current, "RuleTemplateId", "")]
            module.sdk_call(client.DeleteAuditRuleTemplates, request)
            created_id = None
        final = find_template(module, client, models, name)
        module.exit_json(
            changed=True,
            rule_template_name=name,
            rule_template_id=created_id if desired_present else (getattr(final, "RuleTemplateId", "") if final else ""),
            exists=bool(final),
            msg="CDB audit rule template %s" % ("created" if desired_present else "deleted"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud CDB audit rule template request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
