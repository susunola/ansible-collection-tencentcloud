#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: postgresql_backup_plan
short_description: Manage TencentDB for PostgreSQL backup plans
version_added: "0.14.0"
description: Creates, updates and deletes a PostgreSQL backup plan.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: PostgreSQL instance ID.}
  plan_id: {type: str, description: Existing plan ID.}
  name: {type: str, description: Backup plan name.}
  period_type: {type: str, default: week, description: Backup period type.}
  periods: {type: list, elements: str, default: [], description: Backup periods.}
  min_start_time: {type: str, description: Earliest backup start time. Required when C(state=present).}
  max_start_time: {type: str, description: Latest backup start time. Required when C(state=present).}
  retention_days: {type: int, description: Base backup retention days. Required when C(state=present).}
  log_retention_days: {type: int, description: Log backup retention days.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.postgresql_backup_plan:
    instance_id: postgres-xxxxxxxx
    name: production
    periods: [monday, wednesday, friday]
    min_start_time: 03:00:00
    max_start_time: 04:00:00
    retention_days: 30
"""
RETURN = r"""backup_plan: {description: PostgreSQL backup-plan metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.postgres.v20170312 import models, postgres_client

    return models, postgres_client


def build_describe(models, instance_id):
    request = models.DescribeBackupPlansRequest()
    request.DBInstanceId = instance_id
    return request


def apply_request(request, p, plan_id=None):
    request.DBInstanceId, request.PlanName = p["instance_id"], p["name"]
    request.BackupPeriod = sorted(p["periods"])
    request.MinBackupStartTime, request.MaxBackupStartTime = p["min_start_time"], p["max_start_time"]
    request.BaseBackupRetentionPeriod = p["retention_days"]
    if plan_id:
        request.PlanId, request.LogBackupRetentionPeriod = plan_id, p.get("log_retention_days")
    else:
        request.BackupPeriodType = p["period_type"]
    return request


def build_create(models, p):
    return apply_request(models.CreateBackupPlanRequest(), p)


def build_update(models, p, plan_id):
    return apply_request(models.ModifyBackupPlanRequest(), p, plan_id)


def build_delete(models, instance_id, plan_id):
    request = models.DeleteBackupPlanRequest()
    request.DBInstanceId, request.PlanId = instance_id, plan_id
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeBackupPlans, build_describe(models, p["instance_id"]))
    matches = [
        x._serialize(allow_none=True)
        for x in list(response.Plans or [])
        if (p.get("plan_id") and x.PlanId == p["plan_id"]) or (not p.get("plan_id") and x.PlanName == p.get("name"))
    ]
    return matches[0] if matches else None


def desired(p):
    return {
        "PlanName": p["name"],
        "BackupPeriodType": p["period_type"],
        "BackupPeriod": sorted(p["periods"]),
        "MinBackupStartTime": p["min_start_time"],
        "MaxBackupStartTime": p["max_start_time"],
        "BaseBackupRetentionPeriod": p["retention_days"],
        "LogBackupRetentionPeriod": p.get("log_retention_days"),
    }


def comparable(value):
    result = {
        k: value.get(k)
        for k in (
            "PlanName",
            "BackupPeriodType",
            "BackupPeriod",
            "MinBackupStartTime",
            "MaxBackupStartTime",
            "BaseBackupRetentionPeriod",
            "LogBackupRetentionPeriod",
        )
    }
    result["BackupPeriod"] = sorted(result["BackupPeriod"] or [])
    return result


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "plan_id": {},
            "name": {},
            "period_type": {"default": "week"},
            "periods": {"type": "list", "elements": "str", "default": []},
            "min_start_time": {},
            "max_start_time": {},
            "retention_days": {"type": "int"},
            "log_retention_days": {"type": "int"},
        },
        required_one_of=[("plan_id", "name")],
        required_if=[("state", "present", ("name", "min_start_time", "max_start_time", "retention_days"))],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.PostgresClient, "postgres.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, backup_plan=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteBackupPlan, build_delete(models, p["instance_id"], current["PlanId"]))
            module.exit_json(changed=True, **(diff or {}), backup_plan=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, backup_plan=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                require_immutable_unchanged(module, before, target, ("BackupPeriodType",), "PostgreSQL backup plan")
                module.sdk_call(client.ModifyBackupPlan, build_update(models, p, current["PlanId"]))
                p["plan_id"] = current["PlanId"]
            else:
                p["plan_id"] = module.sdk_call(client.CreateBackupPlan, build_create(models, p)).PlanId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), backup_plan=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
