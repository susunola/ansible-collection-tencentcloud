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
  state:
    description:
      - C(present) creates the backup plan with V(CreateBackupPlan) when it does not exist and updates it with
        V(ModifyBackupPlan) when it differs. C(absent) deletes it with V(DeleteBackupPlan).
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - PostgreSQL instance ID.
    type: str
    required: true
  plan_id:
    description:
      - Identifies the backup plan to manage; one of this or O(name) is required.
    type: str
  name:
    description:
      - Identifies the backup plan to manage; one of this or O(plan_id) is required.
    type: str
  period_type:
    description:
      - Backup period type.
    type: str
    default: week
  periods:
    description:
      - Backup periods.
    type: list
    default: []
    elements: str
  min_start_time:
    description:
      - Earliest backup start time. Required when C(state=present).
    type: str
  max_start_time:
    description:
      - Latest backup start time. Required when C(state=present).
    type: str
  retention_days:
    description:
      - Base backup retention days. Required when C(state=present).
    type: int
  log_retention_days:
    description:
      - Log backup retention days.
    type: int

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.postgresql_backup_plan_info
    description: Gather information about Tencent Cloud PostgreSQL backup plans.
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
RETURN = r"""backup_plan:
  description:
    - PostgreSQL backup-plan metadata.
  returned: always
  type: dict"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, fail_from_sdk_error


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
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
