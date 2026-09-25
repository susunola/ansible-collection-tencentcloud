#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cynosdb_backup_config
short_description: Manage Tencent Cloud CynosDB backup configuration
version_added: "0.14.0"
description: Reconciles the automatic backup window and retention duration of a CynosDB cluster.
options:
  cluster_id:
    description:
      - CynosDB cluster ID.
    type: str
    required: true
  backup_start:
    description:
      - Backup window start as seconds after midnight.
    type: int
    default: 10800
  backup_end:
    description:
      - Backup window end as seconds after midnight.
    type: int
    default: 14400
  retention_seconds:
    description:
      - Backup retention duration in seconds.
    type: int
    default: 604800

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
  - module: susunola.tencentcloud.cynosdb_backup_config_info
    description: Gather information about a Tencent Cloud CynosDB backup configuration.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cynosdb_backup_config:
    cluster_id: cynosdbmysql-xxxxxxxx
    backup_start: 10800
    backup_end: 14400
    retention_seconds: 2592000
"""
RETURN = r"""backup_config:
  description:
    - Effective CynosDB backup configuration.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    ClusterId: cynosdbmysql-abc123
    BackupTimeBeg: 10800
    BackupTimeEnd: 14400
    ReserveDuration: 604800
    RequestId: req-fake
    Status: 2
    InstanceName: orders
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.cynosdb.v20190107 import cynosdb_client, models

    return models, cynosdb_client


def describe_request(models, cluster_id):
    request = models.DescribeBackupConfigRequest()
    request.ClusterId = cluster_id
    return request


def update_request(models, p):
    request = models.ModifyBackupConfigRequest()
    request.ClusterId, request.BackupTimeBeg, request.BackupTimeEnd, request.ReserveDuration = (
        p["cluster_id"],
        p["backup_start"],
        p["backup_end"],
        p["retention_seconds"],
    )
    return request


def comparable(value):
    return {
        "BackupTimeBeg": int(value.get("BackupTimeBeg") or 0),
        "BackupTimeEnd": int(value.get("BackupTimeEnd") or 0),
        "ReserveDuration": int(value.get("ReserveDuration") or 0),
    }


def desired(p):
    return {"BackupTimeBeg": p["backup_start"], "BackupTimeEnd": p["backup_end"], "ReserveDuration": p["retention_seconds"]}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "cluster_id": {"required": True},
            "backup_start": {"type": "int", "default": 10800},
            "backup_end": {"type": "int", "default": 14400},
            "retention_seconds": {"type": "int", "default": 604800},
        },
        supports_check_mode=True,
    )
    p = module.params
    if not 0 <= p["backup_start"] < p["backup_end"] <= 86400:
        module.fail_json(msg="backup window must satisfy 0 <= backup_start < backup_end <= 86400")
    if not 604800 <= p["retention_seconds"] <= 158112000:
        module.fail_json(msg="retention_seconds must be between 604800 and 158112000")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CynosdbClient, "cynosdb.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeBackupConfig, describe_request(models, p["cluster_id"]))
        current = response._serialize(allow_none=True)
        before, target = comparable(current), desired(p)
        if before == target:
            module.exit_json(changed=False, backup_config=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyBackupConfig, update_request(models, p))
            response = module.sdk_call(client.DescribeBackupConfig, describe_request(models, p["cluster_id"]))
            current = response._serialize(allow_none=True)
        module.exit_json(changed=True, **(diff or {}), backup_config=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
