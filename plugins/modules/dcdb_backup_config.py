#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: dcdb_backup_config
short_description: Manage Tencent Cloud DCDB automatic backup configuration
version_added: "0.14.0"
description: Reconciles normal backup retention, execution window, weekdays and archive transition.
options:
  instance_id: {type: str, required: true, description: DCDB instance ID.}
  retention_days: {type: int, default: 7, description: Standard backup retention from 1 through 3650 days.}
  start_time: {type: str, default: '22:00', description: Backup window start time.}
  end_time: {type: str, default: '23:59', description: Backup window end time.}
  weekdays: {type: list, elements: str, choices: [Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday], default: [Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday], description: Backup weekdays.}
  archive_after_days: {type: int, default: -1, description: Days before archive transition; minus one disables archive storage.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dcdb_backup_config:
    instance_id: tdsqlshard-xxxxxxxx
    retention_days: 30
    start_time: '02:00'
    end_time: '03:00'
    weekdays: [Monday, Wednesday, Friday]
'''
RETURN = r'''backup_config: {description: Normalized DCDB backup configuration., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _load():
    from tencentcloud.dcdb.v20180411 import models, dcdb_client
    return models, dcdb_client


def describe_request(models, instance_id):
    request = models.DescribeBackupConfigsRequest(); request.InstanceId = instance_id; return request


def modify_request(models, params):
    request = models.ModifyBackupConfigsRequest(); request.InstanceId, request.Days = params["instance_id"], params["retention_days"]
    request.StartBackupTime, request.EndBackupTime = params["start_time"], params["end_time"]
    request.WeekDays = sorted(set(params["weekdays"]), key=WEEKDAYS.index); request.ArchiveDays = params["archive_after_days"]
    return request


def normalize(value):
    if hasattr(value, "_serialize"): value = value._serialize(allow_none=True)
    return {"retention_days": value.get("Days"), "start_time": value.get("StartBackupTime"),
            "end_time": value.get("EndBackupTime"), "weekdays": sorted(value.get("WeekDays") or [], key=WEEKDAYS.index),
            "archive_after_days": value.get("ArchiveDays")}


def desired(params):
    return {"retention_days": params["retention_days"], "start_time": params["start_time"], "end_time": params["end_time"],
            "weekdays": sorted(set(params["weekdays"]), key=WEEKDAYS.index), "archive_after_days": params["archive_after_days"]}


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}, "retention_days": {"type": "int", "default": 7},
        "start_time": {"default": "22:00"}, "end_time": {"default": "23:59"},
        "weekdays": {"type": "list", "elements": "str", "choices": WEEKDAYS, "default": WEEKDAYS},
        "archive_after_days": {"type": "int", "default": -1}}, supports_check_mode=True)
    p = module.params
    if not 1 <= p["retention_days"] <= 3650: module.fail_json(msg="retention_days must be between 1 and 3650")
    if p["archive_after_days"] != -1 and p["archive_after_days"] < 1: module.fail_json(msg="archive_after_days must be -1 or positive")
    module.require_sdk(); models, client_module = _load(); client = module.create_client(client_module.DcdbClient, "dcdb.tencentcloudapi.com")
    try:
        current = normalize(module.sdk_call(client.DescribeBackupConfigs, describe_request(models, p["instance_id"]))); target = desired(p)
        if current == target: module.exit_json(changed=False, backup_config=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyBackupConfigs, modify_request(models, p))
            current = normalize(module.sdk_call(client.DescribeBackupConfigs, describe_request(models, p["instance_id"])))
        module.exit_json(changed=True, **(diff or {}), backup_config=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
