#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: config_remediation
short_description: Manage Tencent Cloud Config remediation settings
version_added: "0.14.0"
description: Creates, updates and deletes automatic or manual remediation bindings for Config rules.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired remediation state.}
  remediation_id: {type: str, description: Existing remediation ID; preferred for updates and deletion.}
  rule_id: {type: str, required: true, description: "Config rule ID, also used for lookup."}
  remediation_type: {type: str, description: Remediation type; required when state is present.}
  remediation_template_id: {type: str, description: Remediation template ID; required when state is present.}
  invoke_type: {type: str, description: Manual or automatic invocation type; required when state is present.}
  source_type: {type: str, description: Remediation source type; required when state is present.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Bind automatic remediation to a Config rule
  susunola.tencentcloud.config_remediation:
    region: ap-guangzhou
    rule_id: cr-xxxxxxxx
    remediation_type: predefined
    remediation_template_id: rt-xxxxxxxx
    invoke_type: AUTO
    source_type: CONFIG
'''

RETURN = r'''remediation: {description: Config remediation metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.config.v20220802 import models, config_client
    return models, config_client


def list_request(models, rule_id):
    request = models.ListRemediationsRequest(); request.Limit, request.RuleIds = 100, [rule_id]; return request


def create_request(models, p):
    request = models.CreateRemediationRequest(); request.RuleId, request.RemediationType = p["rule_id"], p["remediation_type"]
    request.RemediationTemplateId, request.InvokeType, request.SourceType = p["remediation_template_id"], p["invoke_type"], p["source_type"]; return request


def update_request(models, p, remediation_id):
    request = models.UpdateRemediationRequest(); request.RemediationId, request.RemediationType = remediation_id, p["remediation_type"]
    request.RemediationTemplateId, request.InvokeType, request.SourceType = p["remediation_template_id"], p["invoke_type"], p["source_type"]; return request


def delete_request(models, remediation_id):
    request = models.DeleteRemediationsRequest(); request.RemediationIds = [remediation_id]; return request


def find_remediation(module, client, models, p):
    response = module.sdk_call(client.ListRemediations, list_request(models, p["rule_id"])); matches = []
    for value in response.Remediations or []:
        item = value._serialize(allow_none=True)
        if p.get("remediation_id") and item.get("RemediationId") == p["remediation_id"]: matches.append(item)
        elif not p.get("remediation_id") and item.get("RuleId") == p["rule_id"]: matches.append(item)
    if len(matches) > 1: module.fail_json(msg="Multiple remediations matched the rule; specify remediation_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "remediation_id": {}, "rule_id": {"required": True}, "remediation_type": {}, "remediation_template_id": {}, "invoke_type": {}, "source_type": {}}, supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and any(not p.get(key) for key in ("remediation_type", "remediation_template_id", "invoke_type", "source_type")): module.fail_json(msg="remediation_type, remediation_template_id, invoke_type and source_type are required when state=present")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.ConfigClient, "config.tencentcloudapi.com")
    try:
        current = find_remediation(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, remediation=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteRemediations, delete_request(models, current["RemediationId"]))
            module.exit_json(changed=True, **(diff or {}), remediation=current if module.check_mode else None)
        desired = {"RuleId": p["rule_id"], "RemediationType": p["remediation_type"], "RemediationTemplateId": p["remediation_template_id"], "InvokeType": p["invoke_type"], "RemediationSourceType": p["source_type"]}
        before = {key: current.get(key) for key in desired} if current else None
        if before == desired: module.exit_json(changed=False, remediation=current)
        diff = maybe_diff(module, before, desired)
        if not module.check_mode:
            if current: module.sdk_call(client.UpdateRemediation, update_request(models, p, current["RemediationId"]))
            else: p["remediation_id"] = module.sdk_call(client.CreateRemediation, create_request(models, p)).RemediationId
            current = find_remediation(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), remediation=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
