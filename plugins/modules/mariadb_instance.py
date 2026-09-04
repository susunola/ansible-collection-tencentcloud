#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: mariadb_instance
short_description: Manage Tencent Cloud MariaDB instances
version_added: "0.14.0"
description: Creates, renames, resizes, isolates and optionally destroys TencentDB for MariaDB instances.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing MariaDB instance ID.}
  name: {type: str, description: Instance name.}
  zones: {type: list, elements: str, description: Primary and replica availability zones.}
  node_count: {type: int, choices: [2, 3], description: Database node count; defaults to 2 during creation.}
  memory: {type: int, description: Memory in GiB.}
  storage: {type: int, description: Storage in GiB.}
  db_version: {type: str, choices: ['8.0', '5.7', '10.1'], description: Database engine version.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  charge_type: {type: str, choices: [PREPAID, POSTPAID_BY_HOUR], default: POSTPAID_BY_HOUR, description: Billing mode.}
  period_months: {type: int, default: 1, description: Prepaid purchase period in months.}
  auto_renew: {type: bool, default: false, description: Enable prepaid automatic renewal at creation.}
  security_group_ids: {type: list, elements: str, default: [], description: Security groups bound at creation.}
  ipv6: {type: bool, default: false, description: Enable IPv6 at creation.}
  purge: {type: bool, default: false, description: Permanently destroy an already isolated instance.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.mariadb_instance:
    name: production-mariadb
    zones: [ap-guangzhou-3, ap-guangzhou-4]
    memory: 8
    storage: 100
    db_version: '10.1'
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
"""
RETURN = r"""instance: {description: Effective MariaDB instance metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.mariadb.v20170312 import models, mariadb_client

    return models, mariadb_client


def describe_request(models, p):
    request = models.DescribeDBInstancesRequest()
    request.Offset, request.Limit = 0, 100
    if p.get("instance_id"):
        request.InstanceIds = [p["instance_id"]]
    elif p.get("name"):
        request.SearchName = p["name"]
    return request


def _create_fields(request, p):
    request.Zones, request.NodeCount, request.Memory, request.Storage, request.Count = p["zones"], p.get("node_count") or 2, p["memory"], p["storage"], 1
    request.VpcId, request.SubnetId, request.DbVersionId, request.InstanceName = p["vpc_id"], p["subnet_id"], p["db_version"], p["name"]
    request.SecurityGroupIds, request.Ipv6Flag = p["security_group_ids"], 1 if p["ipv6"] else 0
    return request


def create_hour_request(models, p):
    return _create_fields(models.CreateHourDBInstanceRequest(), p)


def create_prepaid_request(models, p):
    request = _create_fields(models.CreateDBInstanceRequest(), p)
    request.Period, request.AutoRenewFlag = p["period_months"], 1 if p["auto_renew"] else 0
    return request


def rename_request(models, instance_id, name):
    request = models.ModifyDBInstanceNameRequest()
    request.InstanceId, request.InstanceName = instance_id, name
    return request


def resize_hour_request(models, p, instance_id):
    request = models.UpgradeHourDBInstanceRequest()
    request.InstanceId, request.Memory, request.Storage, request.Zones = instance_id, p.get("memory"), p.get("storage"), p.get("zones")
    return request


def resize_prepaid_request(models, p, instance_id):
    request = models.UpgradeDBInstanceRequest()
    request.InstanceId, request.Memory, request.Storage, request.Zones = instance_id, p.get("memory"), p.get("storage"), p.get("zones")
    return request


def isolate_request(models, instance_id, hourly):
    request = models.IsolateHourDBInstanceRequest() if hourly else models.IsolateDBInstanceRequest()
    request.InstanceIds = [instance_id]
    return request


def destroy_request(models, instance_id, hourly):
    request = models.DestroyHourDBInstanceRequest() if hourly else models.DestroyDBInstanceRequest()
    request.InstanceId = instance_id
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeDBInstances, describe_request(models, p))
    matches = []
    for item in response.Instances or []:
        value = item._serialize(allow_none=True)
        if (p.get("instance_id") and value.get("InstanceId") == p["instance_id"]) or (not p.get("instance_id") and value.get("InstanceName") == p.get("name")):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple MariaDB instances matched; specify instance_id")
    return matches[0] if matches else None


def hourly(v):
    return str(v.get("Paymode") or "").lower() in ("postpaid", "postpaid_by_hour", "hour")


def _wait(module, client, models, p, states):
    wait_for_state(
        module,
        lambda: (find(module, client, models, p) or {}).get("Status"),
        states,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {},
            "name": {},
            "zones": {"type": "list", "elements": "str"},
            "node_count": {"type": "int", "choices": [2, 3]},
            "memory": {"type": "int"},
            "storage": {"type": "int"},
            "db_version": {"choices": ["8.0", "5.7", "10.1"]},
            "vpc_id": {},
            "subnet_id": {},
            "charge_type": {"choices": ["PREPAID", "POSTPAID_BY_HOUR"], "default": "POSTPAID_BY_HOUR"},
            "period_months": {"type": "int", "default": 1},
            "auto_renew": {"type": "bool", "default": False},
            "security_group_ids": {"type": "list", "elements": "str", "default": []},
            "ipv6": {"type": "bool", "default": False},
            "purge": {"type": "bool", "default": False},
        },
        required_one_of=[("instance_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.MariadbClient, "mariadb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, instance=None)
            is_hourly = hourly(current)
            status = int(current.get("Status"))
            instance_id = current["InstanceId"]
            if p["purge"]:
                if status != -1:
                    module.fail_json(msg="purge requires an already isolated MariaDB instance", current_status=status)
                diff = maybe_diff(module, current, None)
                if not module.check_mode:
                    module.sdk_call(client.DestroyHourDBInstance if is_hourly else client.DestroyDBInstance, destroy_request(models, instance_id, is_hourly))
                module.exit_json(changed=True, **(diff or {}), instance=None)
            if status == -1:
                module.exit_json(changed=False, instance=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.IsolateHourDBInstance if is_hourly else client.IsolateDBInstance, isolate_request(models, instance_id, is_hourly))
                p["instance_id"] = instance_id
                _wait(module, client, models, p, [-1])
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current)
        if not current:
            missing = [key for key in ("name", "zones", "memory", "storage", "db_version", "vpc_id", "subnet_id") if p.get(key) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a new MariaDB instance", missing=missing)
            target = {
                "InstanceName": p["name"],
                "Zone": p["zones"][0],
                "Memory": p["memory"],
                "Storage": p["storage"],
                "DbVersionId": p["db_version"],
                "UniqueVpcId": p["vpc_id"],
                "UniqueSubnetId": p["subnet_id"],
            }
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                if p["charge_type"] == "POSTPAID_BY_HOUR":
                    response = module.sdk_call(client.CreateHourDBInstance, create_hour_request(models, p))
                else:
                    response = module.sdk_call(client.CreateDBInstance, create_prepaid_request(models, p))
                ids = response.InstanceIds or []
                p["instance_id"] = ids[0]
                _wait(module, client, models, p, [2, 3])
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else target)
        drift = {}
        for key, desired_value in (
            ("UniqueVpcId", p.get("vpc_id")),
            ("UniqueSubnetId", p.get("subnet_id")),
            ("DbVersionId", p.get("db_version")),
            ("NodeCount", p.get("node_count")),
        ):
            if desired_value is not None and current.get(key) != desired_value:
                drift[key] = (current.get(key), desired_value)
        if drift:
            module.fail_json(msg="MariaDB network placement, database version and node count are immutable", immutable_drift=drift)
        target = {
            "InstanceName": p.get("name") or current.get("InstanceName"),
            "Zone": p["zones"][0] if p.get("zones") else current.get("Zone"),
            "Memory": p.get("memory") if p.get("memory") is not None else current.get("Memory"),
            "Storage": p.get("storage") if p.get("storage") is not None else current.get("Storage"),
        }
        before = {k: current.get(k) for k in target}
        if before == target:
            module.exit_json(changed=False, instance=current)
        diff = maybe_diff(module, before, target)
        instance_id = current["InstanceId"]
        is_hourly = hourly(current)
        if not module.check_mode:
            if before["InstanceName"] != target["InstanceName"]:
                module.sdk_call(client.ModifyDBInstanceName, rename_request(models, instance_id, target["InstanceName"]))
            if any(before[k] != target[k] for k in ("Zone", "Memory", "Storage")):
                request = resize_hour_request(models, p, instance_id) if is_hourly else resize_prepaid_request(models, p, instance_id)
                module.sdk_call(client.UpgradeHourDBInstance if is_hourly else client.UpgradeDBInstance, request)
                p["instance_id"] = instance_id
                _wait(module, client, models, p, [2, 3])
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), instance=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
