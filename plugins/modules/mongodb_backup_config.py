#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: mongodb_backup_config
short_description: Manage TencentDB for MongoDB automatic backup rules
version_added: "0.14.0"
description: Reconciles automatic backup method, schedule, retention and advanced-backup settings.
options:
  instance_id: {type: str, required: true, description: MongoDB instance ID.}
  backup_method: {type: int, choices: [0, 1, 3], default: 1, description: "Backup method; logical, physical or snapshot."}
  backup_hour: {type: int, default: 2, description: Automatic backup start hour from 0 through 23.}
  frequency_hours: {type: int, choices: [12, 24], default: 24, description: Hours between automatic backups.}
  active_weekdays: {type: list, elements: int, default: [0, 1, 2, 3, 4, 5, 6], description: Backup weekdays where zero is Sunday.}
  retention_days: {type: int, default: 7, description: Full-backup retention in days.}
  oplog_retention_days: {type: int, default: 7, description: Incremental-backup retention in days.}
  backup_version: {type: int, choices: [0, 1], default: 1, description: Legacy or advanced backup mode.}
  alert_threshold: {type: int, default: 100, description: Backup storage usage alert threshold percentage.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.mongodb_backup_config:
    instance_id: cmgo-xxxxxxxx
    backup_hour: 3
    active_weekdays: [1, 2, 3, 4, 5]
    retention_days: 30
'''
RETURN = r'''backup_config: {description: Normalized MongoDB backup rules., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.mongodb.v20190725 import models, mongodb_client
    return models, mongodb_client


def describe_request(models, instance_id):
    request = models.DescribeBackupRulesRequest(); request.InstanceId = instance_id; return request


def set_request(models, p):
    request = models.SetBackupRulesRequest(); request.InstanceId = p["instance_id"]
    request.BackupMethod, request.BackupTime, request.BackupFrequency = p["backup_method"], p["backup_hour"], p["frequency_hours"]
    request.ActiveWeekdays = ",".join(str(x) for x in sorted(set(p["active_weekdays"])))
    request.BackupRetentionPeriod, request.OplogExpiredDays = p["retention_days"], p["oplog_retention_days"]
    request.BackupVersion, request.AlertThreshold = p["backup_version"], p["alert_threshold"]
    return request


def normalize(value):
    if hasattr(value, "_serialize"): value = value._serialize(allow_none=True)
    weekdays = value.get("ActiveWeekdays") or ""
    return {"backup_method": value.get("BackupMethod"), "backup_hour": value.get("BackupTime"), "frequency_hours": value.get("BackupFrequency"), "active_weekdays": sorted(int(x) for x in weekdays.split(",") if x != ""), "retention_days": value.get("BackupSaveTime"), "oplog_retention_days": value.get("OplogExpiredDays"), "backup_version": value.get("BackupVersion"), "alert_threshold": value.get("AlertThreshold")}


def desired(p):
    return {"backup_method": p["backup_method"], "backup_hour": p["backup_hour"], "frequency_hours": p["frequency_hours"], "active_weekdays": sorted(set(p["active_weekdays"])), "retention_days": p["retention_days"], "oplog_retention_days": p["oplog_retention_days"], "backup_version": p["backup_version"], "alert_threshold": p["alert_threshold"]}


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}, "backup_method": {"type": "int", "choices": [0, 1, 3], "default": 1}, "backup_hour": {"type": "int", "default": 2}, "frequency_hours": {"type": "int", "choices": [12, 24], "default": 24}, "active_weekdays": {"type": "list", "elements": "int", "default": [0, 1, 2, 3, 4, 5, 6]}, "retention_days": {"type": "int", "default": 7}, "oplog_retention_days": {"type": "int", "default": 7}, "backup_version": {"type": "int", "choices": [0, 1], "default": 1}, "alert_threshold": {"type": "int", "default": 100}}, supports_check_mode=True)
    p = module.params
    if any(day < 0 or day > 6 for day in p["active_weekdays"]): module.fail_json(msg="active_weekdays entries must be between 0 and 6")
    if p["backup_hour"] < 0 or p["backup_hour"] > 23: module.fail_json(msg="backup_hour must be between 0 and 23")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.MongodbClient, "mongodb.tencentcloudapi.com")
    try:
        current = normalize(module.sdk_call(client.DescribeBackupRules, describe_request(models, p["instance_id"]))); target = desired(p)
        if current == target: module.exit_json(changed=False, backup_config=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.SetBackupRules, set_request(models, p)); current = normalize(module.sdk_call(client.DescribeBackupRules, describe_request(models, p["instance_id"])))
        module.exit_json(changed=True, **(diff or {}), backup_config=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
