#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: redis_backup_config
short_description: Manage TencentDB for Redis automatic backup configuration
version_added: "0.14.0"
description: Reconciles backup weekdays, time period, backup type and retention for a Redis instance.
options:
  instance_id: {type: str, required: true, description: Redis instance ID.}
  week_days: {type: list, elements: str, required: true, description: Backup weekdays.}
  time_period: {type: str, required: true, description: Daily backup time period.}
  backup_type: {type: int, choices: [0, 1, 2], default: 0, description: Automatic backup type.}
  storage_days: {type: int, required: true, description: Backup retention days.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.redis_backup_config:
    instance_id: crs-xxxxxxxx
    week_days: [Monday, Wednesday, Friday]
    time_period: 03:00-04:00
    storage_days: 30
"""
RETURN = r"""backup_config: {description: Effective automatic backup configuration., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.redis.v20180412 import models, redis_client

    return models, redis_client


def build_describe(models, iid):
    request = models.DescribeAutoBackupConfigRequest()
    request.InstanceId = iid
    return request


def build_update(models, p):
    request = models.ModifyAutoBackupConfigRequest()
    request.InstanceId, request.WeekDays, request.TimePeriod, request.AutoBackupType, request.BackupStorageDays = (
        p["instance_id"],
        sorted(p["week_days"]),
        p["time_period"],
        p["backup_type"],
        p["storage_days"],
    )
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "instance_id": {"required": True},
            "week_days": {"type": "list", "elements": "str", "required": True},
            "time_period": {"required": True},
            "backup_type": {"type": "int", "choices": [0, 1, 2], "default": 0},
            "storage_days": {"type": "int", "required": True},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.RedisClient, "redis.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeAutoBackupConfig, build_describe(models, p["instance_id"]))
        current = {
            "WeekDays": sorted(response.WeekDays or []),
            "TimePeriod": response.TimePeriod,
            "AutoBackupType": response.AutoBackupType,
            "BackupStorageDays": response.BackupStorageDays,
        }
        target = {
            "WeekDays": sorted(p["week_days"]),
            "TimePeriod": p["time_period"],
            "AutoBackupType": p["backup_type"],
            "BackupStorageDays": p["storage_days"],
        }
        if current == target:
            module.exit_json(changed=False, backup_config=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyAutoBackupConfig, build_update(models, p))
        module.exit_json(changed=True, **(diff or {}), backup_config=target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
