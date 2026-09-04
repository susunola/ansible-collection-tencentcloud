#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: sqlserver_backup_config
short_description: Manage TencentDB for SQL Server backup configuration
version_added: "0.14.0"
description: Reconciles the regular data and log backup schedule, execution hour, mode and retention period of a SQL Server instance.
options:
  instance_id: {type: str, required: true, description: SQL Server instance ID.}
  backup_type: {type: str, choices: [daily, weekly], default: daily, description: Backup schedule type.}
  backup_hour: {type: int, default: 3, description: Backup start hour from 0 through 23.}
  backup_cycle: {type: list, elements: int, default: [], description: Weekday numbers 1 through 7 used for weekly backups.}
  backup_model:
    type: str
    choices: [master_pkg, master_no_pkg, slave_pkg, slave_no_pkg]
    default: master_pkg
    description: Backup execution and packaging mode.
  retention_days: {type: int, default: 7, description: Data and log backup retention in days.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.sqlserver_backup_config:
    instance_id: mssql-xxxxxxxx
    backup_type: weekly
    backup_hour: 3
    backup_cycle: [1, 3, 5]
    retention_days: 30
"""
RETURN = r"""backup_config: {description: Effective SQL Server backup configuration., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.sqlserver.v20180328 import models, sqlserver_client

    return models, sqlserver_client


def describe_request(models, instance_id):
    request = models.DescribeDBInstancesRequest()
    request.InstanceIdSet, request.Offset, request.Limit = [instance_id], 0, 100
    return request


def update_request(models, p):
    request = models.ModifyBackupStrategyRequest()
    request.InstanceId, request.BackupType, request.BackupTime = p["instance_id"], p["backup_type"], p["backup_hour"]
    request.BackupDay, request.BackupModel, request.BackupSaveDays = 1 if p["backup_type"] == "daily" else None, p["backup_model"], p["retention_days"]
    request.BackupCycle = sorted(set(p["backup_cycle"])) if p["backup_type"] == "weekly" else None
    return request


def find(module, client, models, instance_id):
    response = module.sdk_call(client.DescribeDBInstances, describe_request(models, instance_id))
    for item in response.DBInstances or []:
        value = item._serialize(allow_none=True)
        if value.get("InstanceId") == instance_id:
            return value
    module.fail_json(msg="SQL Server instance was not found", instance_id=instance_id)


def _hour(value):
    if isinstance(value, int):
        return value
    text = str(value or "0")
    return int(text.split(":", 1)[0])


def comparable(value):
    kind = value.get("BackupCycleType") or "daily"
    return {
        "BackupType": kind,
        "BackupTime": _hour(value.get("BackupTime")),
        "BackupCycle": sorted(set(value.get("BackupCycle") or [])) if kind == "weekly" else [],
        "BackupModel": value.get("BackupModel") or "master_pkg",
        "BackupSaveDays": int(value.get("BackupSaveDays") or 7),
    }


def desired(p):
    return {
        "BackupType": p["backup_type"],
        "BackupTime": p["backup_hour"],
        "BackupCycle": sorted(set(p["backup_cycle"])) if p["backup_type"] == "weekly" else [],
        "BackupModel": p["backup_model"],
        "BackupSaveDays": p["retention_days"],
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "instance_id": {"required": True},
            "backup_type": {"choices": ["daily", "weekly"], "default": "daily"},
            "backup_hour": {"type": "int", "default": 3},
            "backup_cycle": {"type": "list", "elements": "int", "default": []},
            "backup_model": {"choices": ["master_pkg", "master_no_pkg", "slave_pkg", "slave_no_pkg"], "default": "master_pkg"},
            "retention_days": {"type": "int", "default": 7},
        },
        supports_check_mode=True,
    )
    p = module.params
    if not 0 <= p["backup_hour"] <= 23:
        module.fail_json(msg="backup_hour must be between 0 and 23")
    if p["backup_type"] == "weekly" and (len(set(p["backup_cycle"])) < 2 or any(day not in range(1, 8) for day in p["backup_cycle"])):
        module.fail_json(msg="weekly backup_cycle must contain at least two unique weekday numbers from 1 through 7")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.SqlserverClient, "sqlserver.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["instance_id"])
        before, target = comparable(current), desired(p)
        if before == target:
            module.exit_json(changed=False, backup_config=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyBackupStrategy, update_request(models, p))
            current = find(module, client, models, p["instance_id"])
        module.exit_json(changed=True, **(diff or {}), backup_config=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
