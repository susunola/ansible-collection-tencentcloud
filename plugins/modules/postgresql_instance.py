#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: postgresql_instance
short_description: Manage Tencent Cloud PostgreSQL instances
version_added: "0.14.0"
description: Creates, renames, resizes, isolates and optionally destroys TencentDB for PostgreSQL instances.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing PostgreSQL instance ID.}
  name: {type: str, description: Instance name.}
  zone: {type: str, description: Primary availability zone; immutable after creation.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  spec_code: {type: str, description: Sales specification code required during creation.}
  storage: {type: int, description: Storage size in GiB, adjustable after creation.}
  cpu: {type: int, description: CPU cores for specification changes.}
  memory: {type: int, description: Memory in GiB for specification changes.}
  major_version: {type: str, description: PostgreSQL major version; immutable after creation.}
  charset: {type: str, choices: [UTF8, LATIN1], default: UTF8, description: Database character set.}
  admin_name: {type: str, default: dbadmin, description: Initial administrator name.}
  admin_password: {type: str, description: Initial administrator password.}
  charge_type: {type: str, choices: [PREPAID, POSTPAID_BY_HOUR], default: POSTPAID_BY_HOUR, description: Billing mode.}
  period_months: {type: int, default: 1, description: Purchase period in months.}
  auto_renew: {type: int, choices: [0, 1, 2], description: Manual renewal, automatic renewal or no renewal for prepaid instances.}
  security_group_ids: {type: list, elements: str, default: [], description: Security groups bound during creation.}
  deletion_protection: {type: bool, default: false, description: Enable deletion protection during creation.}
  purge: {type: bool, default: false, description: Permanently destroy an already isolated instance instead of retaining it in the recycle bin.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 10}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 900}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.postgresql_instance:
    name: production-postgres
    zone: ap-guangzhou-3
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    spec_code: pg.it.medium2
    storage: 100
    major_version: '15'
    admin_password: "{{ vault_postgres_password }}"
'''
RETURN = r'''instance: {description: Effective PostgreSQL instance metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.postgres.v20170312 import models, postgres_client
    return models, postgres_client
def describe_request(models, p, offset=0):
    request = models.DescribeDBInstancesRequest(); request.Offset, request.Limit = offset, 100
    item = models.Filter(); item.Name, item.Values = ("db-instance-id", [p["instance_id"]]) if p.get("instance_id") else ("db-instance-name", [p["name"]]); request.Filters = [item]; return request
def create_request(models, p):
    request = models.CreateInstancesRequest(); request.SpecCode, request.Storage, request.InstanceCount, request.Period = p["spec_code"], p["storage"], 1, p["period_months"]
    request.Charset, request.AdminName, request.AdminPassword = p["charset"], p["admin_name"], p["admin_password"]
    request.Zone, request.DBMajorVersion, request.InstanceChargeType = p["zone"], p["major_version"], p["charge_type"]
    request.VpcId, request.SubnetId, request.AutoRenewFlag, request.Name = p["vpc_id"], p["subnet_id"], 1 if p.get("auto_renew") == 1 else 0, p["name"]
    request.SecurityGroupIds, request.DeletionProtection = p["security_group_ids"], p["deletion_protection"]; return request
def rename_request(models, instance_id, name):
    request = models.ModifyDBInstanceNameRequest(); request.DBInstanceId, request.InstanceName = instance_id, name; return request
def resize_request(models, p, instance_id):
    request = models.ModifyDBInstanceSpecRequest(); request.DBInstanceId, request.Cpu, request.Memory, request.Storage = instance_id, p.get("cpu"), p.get("memory"), p.get("storage"); return request
def renew_request(models, instance_id, flag):
    request = models.SetAutoRenewFlagRequest(); request.DBInstanceIdSet, request.AutoRenewFlag = [instance_id], flag; return request
def isolate_request(models, instance_id):
    request = models.IsolateDBInstancesRequest(); request.DBInstanceIdSet = [instance_id]; return request
def destroy_request(models, instance_id):
    request = models.DestroyDBInstanceRequest(); request.DBInstanceId = instance_id; return request
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeDBInstances, describe_request(models, p)); matches = []
    for item in response.DBInstanceSet or []:
        value = item._serialize(allow_none=True)
        if (p.get("instance_id") and value.get("DBInstanceId") == p["instance_id"]) or (not p.get("instance_id") and value.get("DBInstanceName") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple PostgreSQL instances matched; specify instance_id")
    return matches[0] if matches else None
def _wait(module, client, models, p, states):
    wait_for_state(module, lambda: (find(module, client, models, p) or {}).get("DBInstanceStatus"), states, timeout=module.params["waiter_timeout"], delay=module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {}, "name": {}, "zone": {}, "vpc_id": {}, "subnet_id": {}, "spec_code": {}, "storage": {"type": "int"}, "cpu": {"type": "int"}, "memory": {"type": "int"}, "major_version": {}, "charset": {"choices": ["UTF8", "LATIN1"], "default": "UTF8"}, "admin_name": {"default": "dbadmin"}, "admin_password": {"no_log": True}, "charge_type": {"choices": ["PREPAID", "POSTPAID_BY_HOUR"], "default": "POSTPAID_BY_HOUR"}, "period_months": {"type": "int", "default": 1}, "auto_renew": {"type": "int", "choices": [0, 1, 2]}, "security_group_ids": {"type": "list", "elements": "str", "default": []}, "deletion_protection": {"type": "bool", "default": False}, "purge": {"type": "bool", "default": False}}, required_one_of=[("instance_id", "name")], supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.PostgresClient, "postgres.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, instance=None)
            status = current.get("DBInstanceStatus"); instance_id = current["DBInstanceId"]
            if p["purge"]:
                if status not in ("isolated", "recycled", "offline"): module.fail_json(msg="purge requires an already isolated PostgreSQL instance", current_status=status)
                diff = maybe_diff(module, current, None)
                if not module.check_mode: module.sdk_call(client.DestroyDBInstance, destroy_request(models, instance_id))
                module.exit_json(changed=True, **(diff or {}), instance=None)
            if status in ("isolating", "isolated", "recycling", "recycled", "offline"): module.exit_json(changed=False, instance=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.IsolateDBInstances, isolate_request(models, instance_id)); p["instance_id"] = instance_id; _wait(module, client, models, p, ["isolated", "recycled"]); current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current)
        if not current:
            missing = [key for key in ("name", "zone", "vpc_id", "subnet_id", "spec_code", "storage", "major_version", "admin_password") if p.get(key) is None]
            if missing: module.fail_json(msg="creation parameters are required for a new PostgreSQL instance", missing=missing)
            target = {"DBInstanceName": p["name"], "Zone": p["zone"], "VpcId": p["vpc_id"], "SubnetId": p["subnet_id"], "DBInstanceStorage": p["storage"], "DBMajorVersion": p["major_version"]}; diff = maybe_diff(module, None, target)
            if not module.check_mode:
                ids = module.sdk_call(client.CreateInstances, create_request(models, p)).DBInstanceIdSet or []; p["instance_id"] = ids[0]; _wait(module, client, models, p, ["running"]); current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else target)
        immutable = {"Zone": p.get("zone"), "VpcId": p.get("vpc_id"), "SubnetId": p.get("subnet_id"), "DBMajorVersion": p.get("major_version")}
        drift = {k: (current.get(k), v) for k, v in immutable.items() if v is not None and current.get(k) != v}
        if drift: module.fail_json(msg="PostgreSQL network placement and major version are immutable", immutable_drift=drift)
        desired = {"DBInstanceName": p.get("name") or current.get("DBInstanceName"), "DBInstanceCpu": p.get("cpu") if p.get("cpu") is not None else current.get("DBInstanceCpu"), "DBInstanceMemory": p.get("memory") if p.get("memory") is not None else current.get("DBInstanceMemory"), "DBInstanceStorage": p.get("storage") if p.get("storage") is not None else current.get("DBInstanceStorage"), "AutoRenew": p.get("auto_renew") if p.get("auto_renew") is not None else current.get("AutoRenew")}
        before = {k: current.get(k) for k in desired}
        if before == desired: module.exit_json(changed=False, instance=current)
        diff = maybe_diff(module, before, desired); instance_id = current["DBInstanceId"]
        if not module.check_mode:
            if before["DBInstanceName"] != desired["DBInstanceName"]: module.sdk_call(client.ModifyDBInstanceName, rename_request(models, instance_id, desired["DBInstanceName"]))
            if any(before[k] != desired[k] for k in ("DBInstanceCpu", "DBInstanceMemory", "DBInstanceStorage")):
                module.sdk_call(client.ModifyDBInstanceSpec, resize_request(models, p, instance_id)); p["instance_id"] = instance_id; _wait(module, client, models, p, ["running"])
            if before["AutoRenew"] != desired["AutoRenew"]: module.sdk_call(client.SetAutoRenewFlag, renew_request(models, instance_id, desired["AutoRenew"]))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), instance=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
