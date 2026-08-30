#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: cdb_audit_config
short_description: Manage TencentDB for MySQL audit configuration
version_added: "0.14.0"
description: Enables, configures or closes database audit logging for a CDB instance.
options:
  instance_id: {type: str, required: true, description: CDB instance ID.}
  enabled: {type: bool, default: true, description: Whether database audit logging is enabled.}
  retention_days: {type: int, choices: [7, 30, 180, 365, 1095, 1825], default: 30, description: Audit-log retention while enabled.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cdb_audit_config:
    instance_id: cdb-xxxxxxxx
    enabled: true
    retention_days: 180
'''
RETURN = r'''audit_config: {description: Normalized audit configuration., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cdb.v20170320 import cdb_client, models
    return models, cdb_client


def describe_request(models, instance_id):
    request = models.DescribeAuditConfigRequest(); request.InstanceId = instance_id; return request


def modify_request(models, p):
    request = models.ModifyAuditConfigRequest(); request.InstanceId, request.CloseAudit = p["instance_id"], not p["enabled"]
    if p["enabled"]: request.LogExpireDay = p["retention_days"]
    return request


def normalize(response):
    value = response._serialize(allow_none=True)
    retention = int(value.get("LogExpireDay") or 0)
    return {"enabled": retention > 0 and str(value.get("IsClosing") or "false").lower() != "true", "retention_days": retention}


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}, "enabled": {"type": "bool", "default": True}, "retention_days": {"type": "int", "choices": [7, 30, 180, 365, 1095, 1825], "default": 30}}, supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CdbClient, "cdb.tencentcloudapi.com")
    try:
        current = normalize(module.sdk_call(client.DescribeAuditConfig, describe_request(models, p["instance_id"])))
        target = {"enabled": p["enabled"], "retention_days": p["retention_days"] if p["enabled"] else 0}
        if current == target: module.exit_json(changed=False, audit_config=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyAuditConfig, modify_request(models, p))
            current = normalize(module.sdk_call(client.DescribeAuditConfig, describe_request(models, p["instance_id"])))
        module.exit_json(changed=True, **(diff or {}), audit_config=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
