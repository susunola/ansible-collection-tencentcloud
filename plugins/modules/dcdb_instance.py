#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: dcdb_instance
short_description: Manage Tencent Cloud DCDB instances
version_added: "0.14.0"
description: Creates prepaid or postpaid DCDB instances, renames and expands shards, and performs two-stage removal.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing DCDB instance ID.}
  name: {type: str, description: Instance name.}
  zones: {type: list, elements: str, description: Availability zones; immutable after creation.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  db_version: {type: str, description: Database version ID; immutable after creation.}
  shard_memory: {type: int, description: Memory per shard in GiB.}
  shard_storage: {type: int, description: Storage per shard in GiB.}
  shard_node_count: {type: int, choices: [2, 3], description: Nodes per shard; defaults to 2 during creation.}
  shard_count: {type: int, description: Number of shards; defaults to 2 during creation.}
  shard_cpu: {type: int, description: CPU cores per shard for postpaid creation.}
  charge_type: {type: str, choices: [PREPAID, POSTPAID_BY_HOUR], default: POSTPAID_BY_HOUR, description: Billing mode.}
  period_months: {type: int, default: 1, description: Prepaid purchase period.}
  auto_renew: {type: bool, default: false, description: Automatically renew prepaid instances.}
  security_group_ids: {type: list, elements: str, default: [], description: Security groups bound during creation.}
  ipv6: {type: bool, default: false, description: Enable IPv6 during creation.}
  purge: {type: bool, default: false, description: Permanently destroy an already isolated instance.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dcdb_instance:
    name: production-dcdb
    zones: [ap-guangzhou-3, ap-guangzhou-4]
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    db_version: '8.0'
    shard_memory: 8
    shard_storage: 100
    shard_count: 2
'''
RETURN = r'''instance: {description: Effective DCDB instance metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dcdb.v20180411 import models, dcdb_client
    return models, dcdb_client
def describe_request(models, p, offset=0):
    r = models.DescribeDCDBInstancesRequest(); r.Offset, r.Limit = offset, 100; r.InstanceIds = [p["instance_id"]] if p.get("instance_id") else None; r.SearchName = p.get("name") if not p.get("instance_id") else None; return r
def _create_fields(r, p):
    r.Zones, r.VpcId, r.SubnetId, r.DbVersionId = p["zones"], p["vpc_id"], p["subnet_id"], p["db_version"]
    r.ShardMemory, r.ShardStorage = p["shard_memory"], p["shard_storage"]
    r.ShardNodeCount, r.ShardCount = p.get("shard_node_count") or 2, p.get("shard_count") or 2
    r.Count, r.InstanceName, r.SecurityGroupIds, r.Ipv6Flag = 1, p["name"], p["security_group_ids"], 1 if p["ipv6"] else 0; return r
def create_prepaid_request(models, p):
    r = _create_fields(models.CreateDCDBInstanceRequest(), p); r.Period, r.AutoRenewFlag = p["period_months"], 1 if p["auto_renew"] else 0; return r
def create_hour_request(models, p):
    r = _create_fields(models.CreateHourDCDBInstanceRequest(), p); r.ShardCpu = p.get("shard_cpu"); return r
def rename_request(models, instance_id, name):
    r = models.ModifyDBInstanceNameRequest(); r.InstanceId, r.InstanceName = instance_id, name; return r
def upgrade_request(models, p, current, add_count=0, hourly=True):
    r = models.UpgradeHourDCDBInstanceRequest() if hourly else models.UpgradeDCDBInstanceRequest(); r.InstanceId = current["InstanceId"]
    first = (current.get("ShardDetail") or [{}])[0]
    memory, storage = p.get("shard_memory") or first.get("Memory") or current.get("Memory"), p.get("shard_storage") or first.get("Storage") or current.get("Storage")
    if add_count:
        cfg = models.AddShardConfig(); cfg.ShardCount, cfg.ShardMemory, cfg.ShardStorage = add_count, memory, storage; r.UpgradeType, r.AddShardConfig = "ADD", cfg
    else:
        cfg = models.ExpandShardConfig(); cfg.ShardInstanceIds = [x["ShardInstanceId"] for x in current.get("ShardDetail") or []]; cfg.ShardMemory, cfg.ShardStorage = memory, storage; cfg.ShardNodeCount = p.get("shard_node_count") or first.get("NodeCount") or current.get("NodeCount"); r.UpgradeType, r.ExpandShardConfig = "EXPAND", cfg
    return r
def isolate_request(models, instance_id, hourly=True):
    r = models.IsolateHourDCDBInstanceRequest() if hourly else models.IsolateDCDBInstanceRequest(); r.InstanceIds = [instance_id]; return r
def destroy_request(models, instance_id, hourly=True):
    r = models.DestroyHourDCDBInstanceRequest() if hourly else models.DestroyDCDBInstanceRequest(); r.InstanceId = instance_id; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeDCDBInstances, describe_request(models, p)); matches = []
    for item in response.Instances or []:
        value = item._serialize(allow_none=True)
        if (p.get("instance_id") and value.get("InstanceId") == p["instance_id"]) or (not p.get("instance_id") and value.get("InstanceName") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple DCDB instances matched; specify instance_id")
    return matches[0] if matches else None
def _hourly(current): return str(current.get("Paymode", "")).lower() in ("0", "postpaid", "postpaid_by_hour", "hour")
def _wait(module, client, models, p, states):
    wait_for_state(module, lambda: (find(module, client, models, p) or {}).get("Status"), states, timeout=module.params["waiter_timeout"], delay=module.params["waiter_delay"])


def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {}, "name": {}, "zones": {"type": "list", "elements": "str"}, "vpc_id": {}, "subnet_id": {}, "db_version": {}, "shard_memory": {"type": "int"}, "shard_storage": {"type": "int"}, "shard_node_count": {"type": "int", "choices": [2, 3]}, "shard_count": {"type": "int"}, "shard_cpu": {"type": "int"}, "charge_type": {"choices": ["PREPAID", "POSTPAID_BY_HOUR"], "default": "POSTPAID_BY_HOUR"}, "period_months": {"type": "int", "default": 1}, "auto_renew": {"type": "bool", "default": False}, "security_group_ids": {"type": "list", "elements": "str", "default": []}, "ipv6": {"type": "bool", "default": False}, "purge": {"type": "bool", "default": False}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("instance_id", "name")], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.DcdbClient, "dcdb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, instance=None)
            hourly, status, instance_id = _hourly(current), current.get("Status"), current["InstanceId"]
            if p["purge"]:
                if status not in (-1, 5): module.fail_json(msg="purge requires an already isolated DCDB instance", current_status=status)
                diff = maybe_diff(module, current, None)
                if not module.check_mode: module.sdk_call(client.DestroyHourDCDBInstance if hourly else client.DestroyDCDBInstance, destroy_request(models, instance_id, hourly))
                module.exit_json(changed=True, **(diff or {}), instance=None)
            if status in (-1, 5): module.exit_json(changed=False, instance=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.IsolateHourDCDBInstance if hourly else client.IsolateDCDBInstance, isolate_request(models, instance_id, hourly))
            module.exit_json(changed=True, **(diff or {}), instance=current)
        if not current:
            missing = [k for k in ("name", "zones", "vpc_id", "subnet_id", "db_version", "shard_memory", "shard_storage") if p.get(k) is None]
            if missing: module.fail_json(msg="creation parameters are required for a new DCDB instance", missing=missing)
            target = {"InstanceName": p["name"], "VpcId": p["vpc_id"], "SubnetId": p["subnet_id"], "DbVersionId": p["db_version"], "Memory": p["shard_memory"], "Storage": p["shard_storage"], "ShardCount": p.get("shard_count") or 2, "NodeCount": p.get("shard_node_count") or 2}; diff = maybe_diff(module, None, target)
            if not module.check_mode:
                hourly = p["charge_type"] == "POSTPAID_BY_HOUR"; response = module.sdk_call(client.CreateHourDCDBInstance if hourly else client.CreateDCDBInstance, create_hour_request(models, p) if hourly else create_prepaid_request(models, p)); ids = response.InstanceIds or []; p["instance_id"] = ids[0]; _wait(module, client, models, p, [2]); current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else target)
        immutable = {"VpcId": p.get("vpc_id"), "SubnetId": p.get("subnet_id"), "DbVersionId": p.get("db_version")}; drift = {k: (current.get(k), v) for k, v in immutable.items() if v is not None and current.get(k) != v}
        if drift: module.fail_json(msg="DCDB network placement and database version are immutable", immutable_drift=drift)
        desired = {"InstanceName": p.get("name") or current.get("InstanceName"), "Memory": p.get("shard_memory") if p.get("shard_memory") is not None else current.get("Memory"), "Storage": p.get("shard_storage") if p.get("shard_storage") is not None else current.get("Storage"), "ShardCount": p.get("shard_count") if p.get("shard_count") is not None else current.get("ShardCount"), "NodeCount": p.get("shard_node_count") if p.get("shard_node_count") is not None else current.get("NodeCount")}; before = {k: current.get(k) for k in desired}
        if desired["ShardCount"] < before["ShardCount"] or desired["Memory"] < before["Memory"] or desired["Storage"] < before["Storage"]: module.fail_json(msg="DCDB shard count, memory and storage cannot be reduced")
        if before == desired: module.exit_json(changed=False, instance=current)
        diff = maybe_diff(module, before, desired); instance_id, hourly = current["InstanceId"], _hourly(current)
        if not module.check_mode:
            if before["InstanceName"] != desired["InstanceName"]: module.sdk_call(client.ModifyDBInstanceName, rename_request(models, instance_id, desired["InstanceName"]))
            if any(before[k] != desired[k] for k in ("Memory", "Storage", "NodeCount")):
                module.sdk_call(client.UpgradeHourDCDBInstance if hourly else client.UpgradeDCDBInstance, upgrade_request(models, p, current, hourly=hourly)); p["instance_id"] = instance_id; _wait(module, client, models, p, [2]); current = find(module, client, models, p)
            add_count = desired["ShardCount"] - current.get("ShardCount", 0)
            if add_count: module.sdk_call(client.UpgradeHourDCDBInstance if hourly else client.UpgradeDCDBInstance, upgrade_request(models, p, current, add_count, hourly)); _wait(module, client, models, p, [2])
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), instance=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
