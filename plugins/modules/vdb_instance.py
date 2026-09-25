#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: vdb_instance
short_description: Manage Tencent Cloud VectorDB instances
version_added: "0.14.0"
description: Creates, expands, isolates, recovers and destroys VectorDB instances and reconciles their security groups.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - Existing VectorDB instance ID.
    type: str
  name:
    description:
      - Instance name; immutable after creation.
    type: str
  zone:
    description:
      - Primary availability zone; immutable after creation.
    type: str
  slave_zones:
    description:
      - Secondary availability zones; immutable after creation.
    type: list
    elements: str
  vpc_id:
    description:
      - VPC ID; immutable after creation.
    type: str
  subnet_id:
    description:
      - Subnet ID; immutable after creation.
    type: str
  pay_mode:
    description:
      - Postpaid or prepaid billing mode.
    type: int
    choices: [0, 1]
    default: 0
  pay_period:
    description:
      - Prepaid purchase period in months.
    type: int
    default: 1
  auto_renew:
    description:
      - Prepaid auto-renew flag.
    type: int
    choices: [0, 1]
    default: 0
  product_type:
    description:
      - Numeric VectorDB product type; immutable after creation.
    type: int
  instance_type:
    description:
      - Instance sales type; immutable after creation.
    type: str
  mode:
    description:
      - Deployment mode; immutable after creation.
    type: str
  network_type:
    description:
      - Network type; immutable after creation.
    type: str
  engine_name:
    description:
      - Vector engine name; immutable after creation.
    type: str
  engine_version:
    description:
      - Vector engine version; immutable after creation.
    type: str
  node_type:
    description:
      - Node type; immutable after creation.
    type: str
  cpu:
    description:
      - CPU cores per node.
    type: int
  memory:
    description:
      - Memory in GiB per node.
    type: int
  disk_size:
    description:
      - Storage capacity in GiB.
    type: int
  replica_count:
    description:
      - Desired replica count; expansion only.
    type: int
  worker_node_count:
    description:
      - Initial worker-node count.
    type: int
  security_group_ids:
    description:
      - Full desired security-group set.
    type: list
    elements: str
  tags:
    description:
      - Tags applied during creation.
    type: dict
  project:
    description:
      - Project identifier used during creation.
    type: str
  brief:
    description:
      - Initial instance summary.
    type: str
  chief:
    description:
      - Initial owner.
    type: str
  dba:
    description:
      - Initial DBA contact.
    type: str
  purge:
    description:
      - Permanently destroy an already isolated instance.
    type: bool
    default: false
  recover:
    description:
      - Recover an isolated instance when state is present.
    type: bool
    default: false
  run_now:
    description:
      - Apply scaling immediately.
    type: bool
    default: true

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
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.vdb_instance:
    name: production-vectors
    zone: ap-guangzhou-3
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    product_type: 1
    instance_type: NORMAL
    mode: CLUSTER
    network_type: VPC
    engine_name: VectorDB
    engine_version: '1.0'
    cpu: 4
    memory: 16
    disk_size: 500
    replica_count: 3
"""
RETURN = r"""instance:
  description:
    - Effective VectorDB instance metadata.
  returned: always
  type: dict"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.vdb.v20230616 import models, vdb_client

    return models, vdb_client


def describe_request(models, p, offset=0):
    r = models.DescribeInstancesRequest()
    r.Offset, r.Limit = offset, 100
    r.InstanceIds = [p["instance_id"]] if p.get("instance_id") else None
    r.InstanceNames = [p["name"]] if not p.get("instance_id") and p.get("name") else None
    return r


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.Tag()
        item.TagKey, item.TagValue = key, value
        result.append(item)
    return result


def create_request(models, p):
    r = models.CreateInstanceRequest()
    r.VpcId, r.SubnetId, r.PayMode, r.InstanceName = p["vpc_id"], p["subnet_id"], p["pay_mode"], p["name"]
    r.SecurityGroupIds, r.PayPeriod, r.AutoRenew = p.get("security_group_ids"), p["pay_period"], p["auto_renew"]
    r.ResourceTags, r.Project = _tags(models, p.get("tags")), p.get("project")
    r.ProductType, r.InstanceType, r.Mode, r.NetworkType = p["product_type"], p["instance_type"], p["mode"], p["network_type"]
    r.Zone, r.SlaveZones, r.EngineName, r.EngineVersion = p["zone"], p.get("slave_zones"), p["engine_name"], p["engine_version"]
    r.Brief, r.Chief, r.DBA, r.NodeType = p.get("brief"), p.get("chief"), p.get("dba"), p.get("node_type")
    r.Cpu, r.Memory, r.DiskSize, r.WorkerNodeNum, r.GoodsNum = p["cpu"], p["memory"], p["disk_size"], p.get("worker_node_count"), 1
    return r


def scale_out_request(models, instance_id, replicas, run_now=True):
    r = models.ScaleOutInstanceRequest()
    r.InstanceId, r.ReplicaNum, r.RunNow = instance_id, replicas, run_now
    return r


def scale_up_request(models, p, instance_id):
    r = models.ScaleUpInstanceRequest()
    r.InstanceId, r.Cpu, r.Memory, r.StorageSize, r.RunNow = instance_id, p["cpu"], p["memory"], p["disk_size"], p["run_now"]
    return r


def security_groups_request(models, instance_id, groups):
    r = models.ModifyDBInstanceSecurityGroupsRequest()
    r.InstanceIds, r.SecurityGroupIds = [instance_id], groups
    return r


def isolate_request(models, instance_id):
    r = models.IsolateInstanceRequest()
    r.InstanceId = instance_id
    return r


def recover_request(models, instance_id, period):
    r = models.RecoverInstanceRequest()
    r.InstanceId, r.PayPeriod = instance_id, period
    return r


def destroy_request(models, instance_id):
    r = models.DestroyInstancesRequest()
    r.InstanceIds = [instance_id]
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeInstances, describe_request(models, p))
    matches = []
    for item in response.Items or []:
        value = item._serialize(allow_none=True)
        if (p.get("instance_id") and value.get("InstanceId") == p["instance_id"]) or (not p.get("instance_id") and value.get("Name") == p.get("name")):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple VectorDB instances matched; specify instance_id")
    return matches[0] if matches else None


def _wait(module, client, models, p, states):
    wait_for_state(
        module,
        lambda: str((find(module, client, models, p) or {}).get("Status", "")).lower(),
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
        "slave_zones": {"type": "list", "elements": "str"},
        "vpc_id": {},
        "subnet_id": {},
        "pay_mode": {"type": "int", "choices": [0, 1], "default": 0},
        "pay_period": {"type": "int", "default": 1},
        "auto_renew": {"type": "int", "choices": [0, 1], "default": 0},
        "product_type": {"type": "int"},
        "instance_type": {},
        "mode": {},
        "network_type": {},
        "engine_name": {},
        "engine_version": {},
        "node_type": {},
        "cpu": {"type": "int"},
        "memory": {"type": "int"},
        "disk_size": {"type": "int"},
        "replica_count": {"type": "int"},
        "worker_node_count": {"type": "int"},
        "security_group_ids": {"type": "list", "elements": "str"},
        "tags": {"type": "dict"},
        "project": {},
        "brief": {},
        "chief": {},
        "dba": {},
        "purge": {"type": "bool", "default": False},
        "recover": {"type": "bool", "default": False},
        "run_now": {"type": "bool", "default": True},
    }
    module = TencentCloudModule(
        argument_spec=spec, required_one_of=[("instance_id", "name")], required_together=[("cpu", "memory", "disk_size")], supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.VdbClient, "vdb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, instance=None)
            status, instance_id = str(current.get("Status", "")).lower(), current["InstanceId"]
            if p["purge"]:
                if status not in ("isolated", "isolate"):
                    module.fail_json(msg="purge requires an already isolated VectorDB instance", current_status=status)
                diff = maybe_diff(module, current, None)
                if not module.check_mode:
                    module.sdk_call(client.DestroyInstances, destroy_request(models, instance_id))
                module.exit_json(changed=True, **(diff or {}), instance=None)
            if status in ("isolating", "isolated", "isolate"):
                module.exit_json(changed=False, instance=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.IsolateInstance, isolate_request(models, instance_id))
            module.exit_json(changed=True, **(diff or {}), instance=current)
        if not current:
            missing = [
                k
                for k in (
                    "name",
                    "zone",
                    "vpc_id",
                    "subnet_id",
                    "product_type",
                    "instance_type",
                    "mode",
                    "network_type",
                    "engine_name",
                    "engine_version",
                    "cpu",
                    "memory",
                    "disk_size",
                )
                if p.get(k) is None
            ]
            if missing:
                module.fail_json(msg="creation parameters are required for a new VectorDB instance", missing=missing)
            target = {
                "Name": p["name"],
                "Zone": p["zone"],
                "ProductType": p["product_type"],
                "InstanceType": p["instance_type"],
                "EngineName": p["engine_name"],
                "EngineVersion": p["engine_version"],
                "Cpu": p["cpu"],
                "Memory": p["memory"],
                "Disk": p["disk_size"],
            }
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                ids = module.sdk_call(client.CreateInstance, create_request(models, p)).InstanceIds or []
                p["instance_id"] = ids[0]
                _wait(module, client, models, p, ["running"])
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else target)
        status, instance_id = str(current.get("Status", "")).lower(), current["InstanceId"]
        if status in ("isolated", "isolate"):
            if not p["recover"]:
                module.fail_json(msg="set recover=true to recover an isolated VectorDB instance")
            diff = maybe_diff(module, {"Status": status}, {"Status": "running"})
            if not module.check_mode:
                module.sdk_call(client.RecoverInstance, recover_request(models, instance_id, p["pay_period"]))
                p["instance_id"] = instance_id
                _wait(module, client, models, p, ["running"])
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current)
        networks = {(x.get("VpcId"), x.get("SubnetId")) for x in current.get("Networks") or []}
        immutable = {
            "Name": p.get("name"),
            "Zone": p.get("zone"),
            "ProductType": p.get("product_type"),
            "InstanceType": p.get("instance_type"),
            "EngineName": p.get("engine_name"),
            "EngineVersion": p.get("engine_version"),
            "NodeType": p.get("node_type"),
        }
        drift = {k: (current.get(k), v) for k, v in immutable.items() if v is not None and current.get(k) != v}
        if p.get("vpc_id") and (p["vpc_id"], p.get("subnet_id")) not in networks:
            drift["Network"] = (sorted(networks), (p["vpc_id"], p.get("subnet_id")))
        if drift:
            module.fail_json(msg="VectorDB identity, network and engine fields are immutable", immutable_drift=drift)
        changed = False
        before = {
            "Cpu": current.get("Cpu"),
            "Memory": current.get("Memory"),
            "Disk": current.get("Disk"),
            "ReplicaNum": current.get("ReplicaNum"),
            "SecurityGroupIds": sorted(current.get("SecurityGroupIds") or []),
        }
        desired = {
            "Cpu": p.get("cpu") if p.get("cpu") is not None else current.get("Cpu"),
            "Memory": p.get("memory") if p.get("memory") is not None else current.get("Memory"),
            "Disk": p.get("disk_size") if p.get("disk_size") is not None else current.get("Disk"),
            "ReplicaNum": p.get("replica_count") if p.get("replica_count") is not None else current.get("ReplicaNum"),
            "SecurityGroupIds": sorted(p["security_group_ids"]) if p.get("security_group_ids") is not None else sorted(current.get("SecurityGroupIds") or []),
        }
        for key in ("Cpu", "Memory", "Disk", "ReplicaNum"):
            if desired[key] is not None and before[key] is not None and desired[key] < before[key]:
                module.fail_json(msg="VectorDB compute, storage and replicas cannot be reduced", field=key)
        if before != desired:
            changed = True
            diff = maybe_diff(module, before, desired)
            if not module.check_mode:
                if any(before[k] != desired[k] for k in ("Cpu", "Memory", "Disk")):
                    module.sdk_call(client.ScaleUpInstance, scale_up_request(models, p, instance_id))
                if before["ReplicaNum"] != desired["ReplicaNum"]:
                    module.sdk_call(client.ScaleOutInstance, scale_out_request(models, instance_id, desired["ReplicaNum"], p["run_now"]))
                if before["SecurityGroupIds"] != desired["SecurityGroupIds"]:
                    module.sdk_call(client.ModifyDBInstanceSecurityGroups, security_groups_request(models, instance_id, desired["SecurityGroupIds"]))
                p["instance_id"] = instance_id
                _wait(module, client, models, p, ["running"])
                current = find(module, client, models, p)
        module.exit_json(changed=changed, **((diff if changed else None) or {}), instance=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
