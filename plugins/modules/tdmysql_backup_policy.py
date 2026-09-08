#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tdmysql_backup_policy
short_description: Manage Tencent Cloud TDSQL MySQL backup policy
version_added: "0.14.0"
description:
  - Reconciles the single backup policy returned for an instance.
  - Storage type is derived from the backup method because the API write model accepts it but the read model does not return it.
options:
  instance_id: {type: str, required: true, description: Stable TDSQL MySQL instance ID.}
  backup_start_time: {type: str, description: Backup window start in HH:MM format.}
  backup_end_time: {type: str, description: Backup window end in HH:MM format.}
  backup_method: {type: str, choices: [physical, snapshot], description: Physical or snapshot backup method.}
  enable_full: {type: bool, description: Enable full backups.}
  enable_log: {type: bool, description: Enable log backups.}
  full_retention_days: {type: int, description: Full-backup retention period.}
  log_retention_days: {type: int, description: Log-backup retention period.}
  period_time: {type: str, description: "API weekday expression such as 0,1,2,3,4,5,6."}
  retries: {type: int, default: 5, description: Retries for transient API failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmysql_backup_policy:
    instance_id: tdsql3-xxxxxxxx
    backup_start_time: '00:00'
    backup_end_time: '04:00'
    backup_method: physical
    enable_full: true
    enable_log: true
    full_retention_days: 7
    log_retention_days: 7
    period_time: '0,1,2,3,4,5,6'
"""
RETURN = r"""
backup_policy: {description: Effective backup-policy metadata., type: dict, returned: always}
"""

import json
import re
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tdmysql import _load, backup_policy_describe_request, normalize

FIELDS = {
    "backup_start_time": "BackupStartTime",
    "backup_end_time": "BackupEndTime",
    "backup_method": "BackupMethod",
    "enable_full": "EnableFull",
    "enable_log": "EnableLog",
    "full_retention_days": "FullRetentionPeriod",
    "log_retention_days": "LogRetentionPeriod",
    "period_time": "PeriodTime",
}


def get(module, client, models, instance_id):
    response = module.sdk_call(client.DescribeDBSBackupPolicy, backup_policy_describe_request(models, instance_id))
    items = response.Items or []
    if len(items) != 1:
        module.fail_json(msg="expected exactly one TDSQL MySQL backup policy", instance_id=instance_id, policy_count=len(items))
    return normalize(items[0]._serialize(allow_none=True))


def desired(p, current):
    result = dict(current)
    for source, target in FIELDS.items():
        if p.get(source) is not None:
            result[target] = p[source]
    return normalize(result)


def modify_request(models, p, target):
    value = {key: target.get(key) for key in FIELDS.values()}
    value["InstanceId"] = p["instance_id"]
    value["EnableFull"], value["EnableLog"] = int(bool(value.get("EnableFull"))), int(bool(value.get("EnableLog")))
    value["StorageType"] = "SNAPSHOT" if value.get("BackupMethod") == "snapshot" else "COS"
    request = models.ModifyDBSBackupPolicyRequest()
    request.InstanceId = p["instance_id"]
    request.BackupPolicy = models.BackupPolicyModelInput()
    request.BackupPolicy.from_json_string(json.dumps(value))
    return request


def run_module():
    spec = {
        "instance_id": {"required": True},
        "backup_start_time": {},
        "backup_end_time": {},
        "backup_method": {"choices": ["physical", "snapshot"]},
        "enable_full": {"type": "bool"},
        "enable_log": {"type": "bool"},
        "full_retention_days": {"type": "int"},
        "log_retention_days": {"type": "int"},
        "period_time": {},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if not any(p.get(key) is not None for key in FIELDS):
        module.fail_json(msg="at least one backup policy field is required")
    for key in ("backup_start_time", "backup_end_time"):
        if p.get(key) is not None and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", p[key]):
            module.fail_json(msg="%s must use HH:MM format" % key)
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        current = get(module, client, models, p["instance_id"])
        target = desired(p, current)
        before = {key: current.get(key) for key in FIELDS.values()}
        after = {key: target.get(key) for key in FIELDS.values()}
        if before == after:
            module.exit_json(changed=False, backup_policy=current)
        diff_value = maybe_diff(module, before, after)
        if not module.check_mode:
            response = module.sdk_call(client.ModifyDBSBackupPolicy, modify_request(models, p, target))
            if response.IsSuccess is False:
                module.fail_json(msg="TDSQL MySQL backup policy update failed", detail=response.Msg, request_id=response.RequestId)
            current = get(module, client, models, p["instance_id"])
        module.exit_json(changed=True, **(diff_value or {}), backup_policy=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
