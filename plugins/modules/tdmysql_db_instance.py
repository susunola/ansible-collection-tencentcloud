#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tdmysql_db_instance
short_description: Manage Tencent Cloud TDMysql instances
version_added: "0.14.0"
description: Creates, expands, upgrades, renames, isolates, recovers and permanently destroys TDMysql instances and reconciles security groups and renewal.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing instance ID.}
  name: {type: str, description: Instance display name.}
  zone: {type: str, description: Primary availability zone; immutable after creation.}
  zones: {type: list, elements: str, description: Multi-AZ placement.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  spec_code: {type: str, description: Product specification code.}
  disk: {type: int, description: Storage-node disk size in GiB.}
  storage_node_count: {type: int, description: Storage-node count.}
  replications: {type: int, description: Odd storage replica count; immutable after creation.}
  full_replications: {type: int, description: Full replica count.}
  storage_node_cpu: {type: int, description: CPU cores per storage node.}
  storage_node_memory: {type: int, description: Memory in GiB per storage node.}
  storage_type: {type: str, choices: [CLOUD_HSSD, CLOUD_TCS], description: Storage type.}
  instance_type: {type: str, choices: [separate, hybrid], description: Instance architecture; immutable after creation.}
  instance_mode: {type: str, description: Instance operating mode; immutable after creation.}
  sql_mode: {type: str, choices: [MySQL, HBase], description: Compatibility mode; immutable after creation.}
  create_version: {type: str, description: Initial database version; immutable after creation.}
  instance_count: {type: int, choices: [1], default: 1, description: Number of instances created.}
  pay_mode: {type: str, choices: ['0', '1'], default: '0', description: Postpaid or prepaid billing mode.}
  period_months: {type: int, default: 1, description: Prepaid purchase period.}
  auto_renew: {type: bool, description: Desired prepaid auto-renewal.}
  az_mode: {type: int, choices: [1, 2, 3], description: "Single-AZ, multi-AZ secondary or multi-AZ primary mode."}
  primary_zone: {type: str, description: Primary AZ used when az_mode is 3.}
  port: {type: int, description: Custom database port.}
  template_id: {type: str, description: Initial parameter-template ID.}
  init_params: {type: dict, description: Initial database parameters.}
  auto_scale_min: {type: float, description: Initial minimum serverless CCU.}
  auto_scale_max: {type: float, description: Initial maximum serverless CCU.}
  security_group_ids: {type: list, elements: str, description: Full desired security-group set.}
  username: {type: str, description: Initial administrator username.}
  password: {type: str, description: Initial administrator password.}
  encryption: {type: bool, default: false, description: Enable transparent encryption during creation.}
  tags: {type: dict, description: Tags applied during creation.}
  recover: {type: bool, default: false, description: Recover an isolated instance when state is present.}
  purge: {type: bool, default: false, description: Permanently destroy an already isolated instance.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmysql_db_instance:
    name: production-tdmysql
    zone: ap-guangzhou-3
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    spec_code: tdsql.mysql.x4.medium
    disk: 200
    storage_node_count: 3
    replications: 3
    storage_node_cpu: 4
    storage_node_memory: 16
    password: "{{ vault_tdmysql_password }}"
"""
RETURN = r"""instance: {description: Effective TDMysql instance metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.tdmysql.v20211122 import models, tdmysql_client

    return models, tdmysql_client


def describe_request(models, p, offset=0):
    r = models.DescribeDBInstancesRequest()
    r.Offset, r.Limit = offset, 100
    return r


def detail_request(models, instance_id):
    r = models.DescribeDBInstanceDetailRequest()
    r.InstanceId = instance_id
    return r


def security_groups_describe_request(models, instance_id):
    r = models.DescribeDBSecurityGroupsRequest()
    r.InstanceId = instance_id
    return r


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.ResourceTag()
        item.TagKey, item.TagValue = key, value
        result.append(item)
    return result


def _params(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.InstanceParam()
        item.Param, item.Value = key, str(value)
        result.append(item)
    return result


def create_request(models, p):
    r = models.CreateDBInstancesRequest()
    r.Zone, r.VpcId, r.SubnetId = p["zone"], p["vpc_id"], p["subnet_id"]
    r.SpecCode, r.Disk, r.StorageNodeNum, r.Replications = p["spec_code"], p["disk"], p["storage_node_count"], p["replications"]
    r.InstanceCount, r.FullReplications, r.CreateVersion, r.InstanceName = p["instance_count"], p.get("full_replications"), p.get("create_version"), p["name"]
    r.ResourceTags, r.InitParams = _tags(models, p.get("tags")), _params(models, p.get("init_params"))
    r.TimeUnit, r.TimeSpan, r.PayMode = "m", p["period_months"], p["pay_mode"]
    r.StorageNodeCpu, r.StorageNodeMem = p["storage_node_cpu"], p["storage_node_memory"]
    r.Vport, r.Zones, r.InstanceType = p.get("port"), p.get("zones"), p.get("instance_type")
    r.StorageType, r.AZMode, r.InstanceMode = p.get("storage_type"), p.get("az_mode"), p.get("instance_mode")
    r.TemplateId, r.SQLMode, r.SecurityGroupIds = p.get("template_id"), p.get("sql_mode"), p.get("security_group_ids")
    r.UserName, r.Password, r.EncryptionEnable = p.get("username"), p.get("password"), 1 if p["encryption"] else 0
    if p.get("auto_scale_min") is not None or p.get("auto_scale_max") is not None:
        r.AutoScaleConfig = models.AutoScalingConfig()
        r.AutoScaleConfig.RangeMin, r.AutoScaleConfig.RangeMax = p.get("auto_scale_min"), p.get("auto_scale_max")
    return r


def expand_request(models, p, instance_id, count):
    r = models.ExpandInstanceRequest()
    r.InstanceId, r.StorageNodeNum = instance_id, count
    r.Zones, r.AZMode, r.PrimaryAZ, r.FullReplications = p.get("zones"), p.get("az_mode"), p.get("primary_zone"), p.get("full_replications")
    return r


def upgrade_request(models, p, instance_id, current):
    r = models.UpgradeInstanceRequest()
    r.InstanceId = instance_id
    r.SpecCode = p.get("spec_code") or current.get("SpecCode")
    r.Disk = p.get("disk") if p.get("disk") is not None else current.get("Disk")
    r.StorageNodeCpu = p.get("storage_node_cpu") if p.get("storage_node_cpu") is not None else current.get("StorageNodeCpu")
    r.StorageNodeMem = p.get("storage_node_memory") if p.get("storage_node_memory") is not None else current.get("StorageNodeMem")
    r.StorageType = p.get("storage_type") or current.get("StorageType")
    return r


def rename_request(models, instance_id, name):
    r = models.ModifyInstanceNameRequest()
    r.InstanceId, r.InstanceName = instance_id, name
    return r


def isolate_request(models, instance_id):
    r = models.IsolateDBInstanceRequest()
    r.InstanceIds = [instance_id]
    return r


def recover_request(models, instance_id):
    r = models.CancelIsolateDBInstancesRequest()
    r.InstanceIds = [instance_id]
    return r


def destroy_request(models, instance_id):
    r = models.DestroyInstancesRequest()
    r.InstanceIds = [instance_id]
    return r


def renew_request(models, instance_id, enabled):
    r = models.ModifyAutoRenewFlagRequest()
    r.InstanceIds, r.AutoRenewFlag = [instance_id], 1 if enabled else 0
    return r


def security_groups_request(models, instance_id, groups):
    r = models.ModifyDBInstanceSecurityGroupsRequest()
    r.InstanceId, r.SecurityGroupIds = instance_id, groups
    return r


def find(module, client, models, p):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeDBInstances, describe_request(models, p, offset))
        items = response.Instances or []
        for item in items:
            value = item._serialize(allow_none=True)
            if (p.get("instance_id") and value.get("InstanceId") == p["instance_id"]) or (
                not p.get("instance_id") and value.get("InstanceName") == p.get("name")
            ):
                matches.append(value)
        offset += len(items)
        if not items or offset >= (response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TDMysql instances matched; specify instance_id")
    if matches:
        detail = module.sdk_call(client.DescribeDBInstanceDetail, detail_request(models, matches[0]["InstanceId"]))._serialize(allow_none=True)
        detail.pop("RequestId", None)
        matches[0].update(detail)
    if matches and p.get("security_group_ids") is not None:
        response = module.sdk_call(client.DescribeDBSecurityGroups, security_groups_describe_request(models, matches[0]["InstanceId"]))
        matches[0]["SecurityGroupIds"] = sorted(group.SecurityGroupId for group in response.Groups or [])
    return matches[0] if matches else None


def _wait(module, client, models, p, states):
    wait_for_state(
        module,
        lambda: str((find(module, client, models, p) or {}).get("Status", "absent")).lower(),
        states,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {},
        "name": {},
        "zone": {},
        "zones": {"type": "list", "elements": "str"},
        "vpc_id": {},
        "subnet_id": {},
        "spec_code": {},
        "disk": {"type": "int"},
        "storage_node_count": {"type": "int"},
        "replications": {"type": "int"},
        "full_replications": {"type": "int"},
        "storage_node_cpu": {"type": "int"},
        "storage_node_memory": {"type": "int"},
        "storage_type": {"choices": ["CLOUD_HSSD", "CLOUD_TCS"]},
        "instance_type": {"choices": ["separate", "hybrid"]},
        "instance_mode": {},
        "sql_mode": {"choices": ["MySQL", "HBase"]},
        "create_version": {},
        "instance_count": {"type": "int", "choices": [1], "default": 1},
        "pay_mode": {"choices": ["0", "1"], "default": "0"},
        "period_months": {"type": "int", "default": 1},
        "auto_renew": {"type": "bool"},
        "az_mode": {"type": "int", "choices": [1, 2, 3]},
        "primary_zone": {},
        "port": {"type": "int"},
        "template_id": {},
        "init_params": {"type": "dict"},
        "auto_scale_min": {"type": "float"},
        "auto_scale_max": {"type": "float"},
        "security_group_ids": {"type": "list", "elements": "str"},
        "username": {},
        "password": {"no_log": True},
        "encryption": {"type": "bool", "default": False},
        "tags": {"type": "dict"},
        "recover": {"type": "bool", "default": False},
        "purge": {"type": "bool", "default": False},
    }
    module = TencentCloudModule(
        argument_spec=spec, required_one_of=[("instance_id", "name")], required_together=[("auto_scale_min", "auto_scale_max")], supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, instance=None)
            status, instance_id = str(current.get("Status", "")).lower(), current["InstanceId"]
            if p["purge"]:
                if status != "isolated":
                    module.fail_json(msg="purge requires an already isolated TDMysql instance", current_status=status)
                diff = maybe_diff(module, current, None)
                if not module.check_mode:
                    module.sdk_call(client.DestroyInstances, destroy_request(models, instance_id))
                    p["instance_id"] = instance_id
                    _wait(module, client, models, p, ["absent", "destroyed"])
                module.exit_json(changed=True, **(diff or {}), instance=None)
            if status in ("isolating", "isolated"):
                module.exit_json(changed=False, instance=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.IsolateDBInstance, isolate_request(models, instance_id))
                p["instance_id"] = instance_id
                _wait(module, client, models, p, ["isolated"])
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current)
        if not current:
            missing = [
                key
                for key in (
                    "name",
                    "zone",
                    "vpc_id",
                    "subnet_id",
                    "spec_code",
                    "disk",
                    "storage_node_count",
                    "replications",
                    "storage_node_cpu",
                    "storage_node_memory",
                    "password",
                )
                if p.get(key) is None
            ]
            if missing:
                module.fail_json(msg="creation parameters are required for a new TDMysql instance", missing=missing)
            target = {
                "InstanceName": p["name"],
                "Zone": p["zone"],
                "VpcId": p["vpc_id"],
                "SubnetId": p["subnet_id"],
                "Disk": p["disk"],
                "StorageNodeNum": p["storage_node_count"],
                "Replications": p["replications"],
                "StorageNodeCpu": p["storage_node_cpu"],
                "StorageNodeMem": p["storage_node_memory"],
                "PayMode": p["pay_mode"],
            }
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                ids = module.sdk_call(client.CreateDBInstances, create_request(models, p)).InstanceIds or []
                p["instance_id"] = ids[0]
                _wait(module, client, models, p, ["running"])
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else target)
        status, instance_id = str(current.get("Status", "")).lower(), current["InstanceId"]
        if status == "isolating" and p["recover"]:
            p["instance_id"] = instance_id
            _wait(module, client, models, p, ["isolated"])
            current = find(module, client, models, p)
            status = "isolated"
        if status == "isolated":
            if not p["recover"]:
                module.fail_json(msg="set recover=true to recover an isolated TDMysql instance")
            diff = maybe_diff(module, {"Status": status}, {"Status": "running"})
            if not module.check_mode:
                module.sdk_call(client.CancelIsolateDBInstances, recover_request(models, instance_id))
                p["instance_id"] = instance_id
                _wait(module, client, models, p, ["running"])
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current)
        if status in ("creating", "initializing", "modifying"):
            p["instance_id"] = instance_id
            _wait(module, client, models, p, ["running"])
            current = find(module, client, models, p)
        immutable = {
            "Zone": p.get("zone"),
            "VpcId": p.get("vpc_id"),
            "SubnetId": p.get("subnet_id"),
            "Replications": p.get("replications"),
            "InstanceType": p.get("instance_type"),
            "InstanceMode": p.get("instance_mode"),
            "SQLMode": p.get("sql_mode"),
            "CreateVersion": p.get("create_version"),
        }
        drift = {key: (current.get(key), value) for key, value in immutable.items() if value is not None and current.get(key) != value}
        if drift:
            module.fail_json(msg="TDMysql placement, architecture, replica and compatibility fields are immutable", immutable_drift=drift)
        before = {
            "InstanceName": current.get("InstanceName"),
            "Disk": current.get("Disk"),
            "StorageNodeNum": current.get("StorageNodeNum"),
            "StorageNodeCpu": current.get("StorageNodeCpu"),
            "StorageNodeMem": current.get("StorageNodeMem"),
            "StorageType": current.get("StorageType"),
            "RenewFlag": current.get("RenewFlag"),
            "SecurityGroupIds": sorted(current.get("SecurityGroupIds") or []),
        }
        desired = {
            "InstanceName": p.get("name") or before["InstanceName"],
            "Disk": p.get("disk") if p.get("disk") is not None else before["Disk"],
            "StorageNodeNum": p.get("storage_node_count") if p.get("storage_node_count") is not None else before["StorageNodeNum"],
            "StorageNodeCpu": p.get("storage_node_cpu") if p.get("storage_node_cpu") is not None else before["StorageNodeCpu"],
            "StorageNodeMem": p.get("storage_node_memory") if p.get("storage_node_memory") is not None else before["StorageNodeMem"],
            "StorageType": p.get("storage_type") or before["StorageType"],
            "RenewFlag": (1 if p["auto_renew"] else 0) if p.get("auto_renew") is not None else before["RenewFlag"],
            "SecurityGroupIds": sorted(p["security_group_ids"]) if p.get("security_group_ids") is not None else before["SecurityGroupIds"],
        }
        for key in ("Disk", "StorageNodeNum", "StorageNodeCpu", "StorageNodeMem"):
            if desired[key] is not None and before[key] is not None and desired[key] < before[key]:
                module.fail_json(msg="TDMysql storage topology cannot be reduced", field=key)
        if before == desired:
            module.exit_json(changed=False, instance=current)
        diff = maybe_diff(module, before, desired)
        if not module.check_mode:
            if before["InstanceName"] != desired["InstanceName"]:
                module.sdk_call(client.ModifyInstanceName, rename_request(models, instance_id, desired["InstanceName"]))
            if before["StorageNodeNum"] != desired["StorageNodeNum"]:
                module.sdk_call(client.ExpandInstance, expand_request(models, p, instance_id, desired["StorageNodeNum"]))
                _wait(module, client, models, p, ["running"])
                current = find(module, client, models, p)
            if any(before[key] != desired[key] for key in ("Disk", "StorageNodeCpu", "StorageNodeMem", "StorageType")):
                module.sdk_call(client.UpgradeInstance, upgrade_request(models, p, instance_id, current))
                _wait(module, client, models, p, ["running"])
            if before["RenewFlag"] != desired["RenewFlag"]:
                module.sdk_call(client.ModifyAutoRenewFlag, renew_request(models, instance_id, bool(desired["RenewFlag"])))
            if before["SecurityGroupIds"] != desired["SecurityGroupIds"]:
                module.sdk_call(client.ModifyDBInstanceSecurityGroups, security_groups_request(models, instance_id, desired["SecurityGroupIds"]))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), instance=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
