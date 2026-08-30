#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: sqlserver_instance
short_description: Manage TencentDB for SQL Server instances
version_added: "0.14.0"
description: Creates, renames, resizes, isolates and optionally destroys TencentDB for SQL Server instances.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing instance ID.}
  name: {type: str, description: Instance name.}
  zone: {type: str, description: Availability zone; immutable after creation.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  memory: {type: int, description: Memory in GiB.}
  storage: {type: int, description: Storage in GiB.}
  cpu: {type: int, description: CPU cores for specification changes.}
  db_version: {type: str, description: SQL Server version identifier.}
  charge_type: {type: str, choices: [PREPAID, POSTPAID], default: POSTPAID, description: Billing mode.}
  period_months: {type: int, default: 1, description: Prepaid purchase period.}
  auto_renew: {type: bool, default: false, description: Automatically renew prepaid instances.}
  security_group_ids: {type: list, elements: str, default: [], description: Bound security groups.}
  ha_type: {type: str, description: High availability type.}
  secondary_zones: {type: list, elements: str, description: Secondary availability zones.}
  purge: {type: bool, default: false, description: Permanently delete an already isolated instance.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.sqlserver_instance:
    name: production-sqlserver
    zone: ap-guangzhou-3
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    memory: 8
    storage: 100
    db_version: '2019'
'''
RETURN = r'''instance: {description: Effective SQL Server instance metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.sqlserver.v20180328 import models, sqlserver_client
    return models, sqlserver_client
def describe_request(models, p, offset=0):
    r = models.DescribeDBInstancesRequest(); r.Offset, r.Limit = offset, 100
    r.InstanceIdSet = [p["instance_id"]] if p.get("instance_id") else None
    r.InstanceNameSet = [p["name"]] if not p.get("instance_id") and p.get("name") else None; return r
def create_request(models, p):
    r = models.CreateDBInstancesRequest(); r.Zone, r.Memory, r.Storage = p["zone"], p["memory"], p["storage"]
    r.InstanceChargeType, r.GoodsNum, r.Period = p["charge_type"], 1, p["period_months"]
    r.VpcId, r.SubnetId, r.DBVersion = p["vpc_id"], p["subnet_id"], p["db_version"]
    r.AutoRenewFlag, r.SecurityGroupList = 1 if p["auto_renew"] else 0, p["security_group_ids"]
    r.HAType, r.MultiZones, r.DrZones = p.get("ha_type"), bool(p.get("secondary_zones")), p.get("secondary_zones"); return r
def rename_request(models, instance_id, name):
    r = models.ModifyDBInstanceNameRequest(); r.InstanceId, r.InstanceName = instance_id, name; return r
def resize_request(models, p, instance_id):
    r = models.UpgradeDBInstanceRequest(); r.InstanceId, r.Memory, r.Storage, r.Cpu = instance_id, p.get("memory"), p.get("storage"), p.get("cpu")
    r.DBVersion, r.HAType, r.MultiZones, r.DrZones = p.get("db_version"), p.get("ha_type"), "true" if p.get("secondary_zones") else "false", p.get("secondary_zones"); return r
def security_groups_request(models, instance_id, groups):
    r = models.ModifyDBInstanceSecurityGroupsRequest(); r.InstanceId, r.SecurityGroupIdSet = instance_id, groups; return r
def renew_request(models, instance_id, enabled):
    item = models.InstanceRenewInfo(); item.InstanceId, item.RenewFlag = instance_id, 1 if enabled else 0
    r = models.ModifyDBInstanceRenewFlagRequest(); r.RenewFlags = [item]; return r
def isolate_request(models, instance_id):
    r = models.TerminateDBInstanceRequest(); r.InstanceIdSet = [instance_id]; return r
def destroy_request(models, instance_id):
    r = models.DeleteDBInstanceRequest(); r.InstanceId = instance_id; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeDBInstances, describe_request(models, p)); matches = []
    for item in response.DBInstances or []:
        value = item._serialize(allow_none=True)
        if (p.get("instance_id") and value.get("InstanceId") == p["instance_id"]) or (not p.get("instance_id") and value.get("Name") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple SQL Server instances matched; specify instance_id")
    return matches[0] if matches else None
def _wait(module, client, models, p, states):
    wait_for_state(module, lambda: (find(module, client, models, p) or {}).get("Status"), states, timeout=module.params["waiter_timeout"], delay=module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {}, "name": {}, "zone": {}, "vpc_id": {}, "subnet_id": {}, "memory": {"type": "int"}, "storage": {"type": "int"}, "cpu": {"type": "int"}, "db_version": {}, "charge_type": {"choices": ["PREPAID", "POSTPAID"], "default": "POSTPAID"}, "period_months": {"type": "int", "default": 1}, "auto_renew": {"type": "bool", "default": False}, "security_group_ids": {"type": "list", "elements": "str", "default": []}, "ha_type": {}, "secondary_zones": {"type": "list", "elements": "str"}, "purge": {"type": "bool", "default": False}}, required_one_of=[("instance_id", "name")], supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.SqlserverClient, "sqlserver.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, instance=None)
            instance_id, status = current["InstanceId"], current.get("Status")
            if p["purge"]:
                if status not in (5, -1): module.fail_json(msg="purge requires an already isolated SQL Server instance", current_status=status)
                diff = maybe_diff(module, current, None)
                if not module.check_mode: module.sdk_call(client.DeleteDBInstance, destroy_request(models, instance_id))
                module.exit_json(changed=True, **(diff or {}), instance=None)
            if status in (5, -1): module.exit_json(changed=False, instance=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.TerminateDBInstance, isolate_request(models, instance_id))
            module.exit_json(changed=True, **(diff or {}), instance=current)
        if not current:
            missing = [k for k in ("name", "zone", "vpc_id", "subnet_id", "memory", "storage", "db_version") if p.get(k) is None]
            if missing: module.fail_json(msg="creation parameters are required for a new SQL Server instance", missing=missing)
            target = {"Name": p["name"], "Zone": p["zone"], "UniqVpcId": p["vpc_id"], "UniqSubnetId": p["subnet_id"], "Memory": p["memory"], "Storage": p["storage"], "Version": p["db_version"]}; diff = maybe_diff(module, None, target)
            if not module.check_mode: module.sdk_call(client.CreateDBInstances, create_request(models, p)); _wait(module, client, models, p, [2]); current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else target)
        immutable = {"Zone": p.get("zone"), "UniqVpcId": p.get("vpc_id"), "UniqSubnetId": p.get("subnet_id")}; drift = {k: (current.get(k), v) for k, v in immutable.items() if v is not None and current.get(k) != v}
        if drift: module.fail_json(msg="SQL Server network placement is immutable", immutable_drift=drift)
        desired = {"Name": p.get("name") or current.get("Name"), "Memory": p.get("memory") if p.get("memory") is not None else current.get("Memory"), "Storage": p.get("storage") if p.get("storage") is not None else current.get("Storage"), "Cpu": p.get("cpu") if p.get("cpu") is not None else current.get("Cpu"), "Version": p.get("db_version") if p.get("db_version") is not None else current.get("Version")}
        before = {k: current.get(k) for k in desired}
        if before == desired: module.exit_json(changed=False, instance=current)
        diff = maybe_diff(module, before, desired); instance_id = current["InstanceId"]
        if not module.check_mode:
            if before["Name"] != desired["Name"]: module.sdk_call(client.ModifyDBInstanceName, rename_request(models, instance_id, desired["Name"]))
            if any(before[k] != desired[k] for k in ("Memory", "Storage", "Cpu", "Version")): module.sdk_call(client.UpgradeDBInstance, resize_request(models, p, instance_id)); p["instance_id"] = instance_id; _wait(module, client, models, p, [2])
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), instance=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
