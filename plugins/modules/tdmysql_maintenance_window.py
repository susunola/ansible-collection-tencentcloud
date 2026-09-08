#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tdmysql_maintenance_window
short_description: Manage Tencent Cloud TDSQL MySQL maintenance windows
version_added: "0.14.0"
description:
  - Reconciles the weekly maintenance days, start time and one-to-three-hour duration.
  - Normalizes API C(HH:MM-HH:MM) ranges and accepts C(HH:MM) or C(HH:MM:SS) start times.
options:
  instance_id: {type: str, required: true, description: Stable TDSQL MySQL instance ID.}
  start_time: {type: str, required: true, description: Maintenance start time in HH:MM or HH:MM:SS format.}
  duration_hours: {type: int, choices: [1, 2, 3], required: true, description: Maintenance duration in hours.}
  week_days: {type: list, elements: str, required: true, description: Non-empty weekday set.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmysql_maintenance_window:
    instance_id: tdsql3-xxxxxxxx
    start_time: '02:00'
    duration_hours: 2
    week_days: [Tuesday, Saturday]
"""
RETURN = r"""
maintenance_window: {description: Effective normalized window and weekdays., type: dict, returned: always}
"""

import re
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _load():
    from tencentcloud.tdmysql.v20211122 import models, tdmysql_client

    return models, tdmysql_client


def normalize_start(value):
    match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?", value or "")
    if not match:
        raise ValueError("start_time must use HH:MM or HH:MM:SS")
    return "%s:%s" % (match.group(1), match.group(2))


def expected_range(start, duration):
    start = normalize_start(start)
    hour, minute = (int(x) for x in start.split(":"))
    end_minutes = (hour * 60 + minute + duration * 60) % 1440
    return "%s-%02d:%02d" % (start, end_minutes // 60, end_minutes % 60)


def describe_request(models, instance_id):
    request = models.DescribeMaintenanceWindowRequest()
    request.InstanceId = instance_id
    return request


def modify_request(models, p):
    request = models.ModifyMaintenanceWindowRequest()
    request.InstanceId = p["instance_id"]
    request.StartTime, request.Duration, request.WeekDays = (
        normalize_start(p["start_time"]) + ":00",
        p["duration_hours"],
        sorted(p["week_days"], key=DAYS.index),
    )
    return request


def get(module, client, models, instance_id):
    response = module.sdk_call(client.DescribeMaintenanceWindow, describe_request(models, instance_id))
    return {"InstanceId": instance_id, "MaintenanceWindow": response.MaintenanceWindow, "WeekDays": sorted(response.WeekDays or [], key=DAYS.index)}


def run_module():
    spec = {
        "instance_id": {"required": True},
        "start_time": {"required": True},
        "duration_hours": {"type": "int", "choices": [1, 2, 3], "required": True},
        "week_days": {"type": "list", "elements": "str", "required": True, "choices": DAYS},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    try:
        normalize_start(p["start_time"])
    except ValueError as exc:
        module.fail_json(msg=str(exc))
    if not p["week_days"] or len(p["week_days"]) != len(set(p["week_days"])):
        module.fail_json(msg="week_days must be non-empty and unique")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        current = get(module, client, models, p["instance_id"])
        target = {
            "InstanceId": p["instance_id"],
            "MaintenanceWindow": expected_range(p["start_time"], p["duration_hours"]),
            "WeekDays": sorted(p["week_days"], key=DAYS.index),
        }
        if current == target:
            module.exit_json(changed=False, maintenance_window=current)
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyMaintenanceWindow, modify_request(models, p))
            current = get(module, client, models, p["instance_id"])
        module.exit_json(changed=True, **(diff_value or {}), maintenance_window=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
