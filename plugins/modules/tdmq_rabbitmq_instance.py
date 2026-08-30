#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tdmq_rabbitmq_instance
short_description: Manage Tencent Cloud TDMQ RabbitMQ dedicated instances
version_added: "0.14.0"
description: Creates, updates and deletes RabbitMQ dedicated instances used by the TDMQ RabbitMQ resource family.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing instance ID.}
  name: {type: str, description: Cluster name.}
  zone_ids: {type: list, elements: int, description: Numeric availability-zone IDs; immutable after creation.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  node_spec: {type: str, default: rabbit-vip-basic-1, description: RabbitMQ node sales specification.}
  node_count: {type: int, description: Node count; defaults to one for single-zone and three for multi-zone creation.}
  storage_size: {type: int, default: 200, description: Storage per node in GiB.}
  cluster_version: {type: str, choices: ['3.8.30', '3.11.8', '3.13.7'], description: RabbitMQ version; defaults to 3.11.8 during creation.}
  pay_mode: {type: int, choices: [0, 1], default: 0, description: Postpaid or prepaid billing mode.}
  period_months: {type: int, default: 1, description: Prepaid purchase period.}
  auto_renew: {type: bool, default: true, description: Automatically renew prepaid instances.}
  default_ha_mirror_queue: {type: bool, default: false, description: Create the default high-availability mirror queue policy.}
  bandwidth: {type: int, description: Public bandwidth in Mbps.}
  public_access: {type: bool, default: false, description: Enable public access during creation.}
  deletion_protection: {type: bool, description: Enable deletion protection.}
  remark: {type: str, description: Instance remark.}
  tags: {type: dict, description: Full desired tag set.}
  international: {type: bool, default: false, description: Use the international-site purchase path.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdmq_rabbitmq_instance:
    name: production-rabbitmq
    zone_ids: [100003, 100004, 100005]
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    node_spec: rabbit-vip-profession-4c16g
    node_count: 3
    storage_size: 500
    cluster_version: '3.13.7'
    deletion_protection: true
'''
RETURN = r'''instance: {description: Effective RabbitMQ dedicated-instance metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client
    return models, tdmq_client
def describe_request(models, p, offset=0):
    r = models.DescribeRabbitMQVipInstancesRequest(); r.Offset, r.Limit = offset, 100
    if p.get("instance_id") or p.get("name"):
        f = models.Filter(); f.Name, f.Values = ("instanceId", [p["instance_id"]]) if p.get("instance_id") else ("instanceName", [p["name"]]); r.Filters = [f]
    return r
def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.Tag(); item.TagKey, item.TagValue = key, value; result.append(item)
    return result
def create_request(models, p):
    r = models.CreateRabbitMQVipInstanceRequest(); r.ZoneIds, r.VpcId, r.SubnetId, r.ClusterName = p["zone_ids"], p["vpc_id"], p["subnet_id"], p["name"]
    r.NodeSpec, r.NodeNum, r.StorageSize, r.ClusterVersion = p["node_spec"], p.get("node_count") or (3 if len(p["zone_ids"]) > 1 else 1), p["storage_size"], p.get("cluster_version") or "3.11.8"
    r.EnableCreateDefaultHaMirrorQueue, r.AutoRenewFlag, r.TimeSpan, r.PayMode = p["default_ha_mirror_queue"], p["auto_renew"], p["period_months"], p["pay_mode"]
    r.Bandwidth, r.EnablePublicAccess = p.get("bandwidth"), p["public_access"]; r.EnableDeletionProtection = bool(p.get("deletion_protection")); r.IsIntl, r.ResourceTags = p["international"], _tags(models, p.get("tags")); return r
def modify_request(models, p, instance_id):
    r = models.ModifyRabbitMQVipInstanceRequest(); r.InstanceId, r.ClusterName, r.Remark = instance_id, p.get("name"), p.get("remark"); r.EnableDeletionProtection = p.get("deletion_protection")
    if p.get("tags") is not None: r.Tags, r.RemoveAllTags = _tags(models, p["tags"]), not bool(p["tags"])
    return r
def delete_request(models, instance_id, international=False):
    r = models.DeleteRabbitMQVipInstanceRequest(); r.InstanceId, r.IsIntl = instance_id, international; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeRabbitMQVipInstances, describe_request(models, p)); matches = []
    for item in response.Instances or []:
        value = item._serialize(allow_none=True)
        if (p.get("instance_id") and value.get("InstanceId") == p["instance_id"]) or (not p.get("instance_id") and value.get("InstanceName") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple RabbitMQ instances matched; specify instance_id")
    return matches[0] if matches else None
def _wait(module, client, models, p, states):
    wait_for_state(module, lambda: (find(module, client, models, p) or {}).get("ClusterStatus"), states, timeout=module.params["waiter_timeout"], delay=module.params["waiter_delay"])
def _tag_map(current): return {x.get("TagKey"): x.get("TagValue") for x in current.get("Tags") or []}


def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {}, "name": {}, "zone_ids": {"type": "list", "elements": "int"}, "vpc_id": {}, "subnet_id": {}, "node_spec": {"default": "rabbit-vip-basic-1"}, "node_count": {"type": "int"}, "storage_size": {"type": "int", "default": 200}, "cluster_version": {"choices": ["3.8.30", "3.11.8", "3.13.7"]}, "pay_mode": {"type": "int", "choices": [0, 1], "default": 0}, "period_months": {"type": "int", "default": 1}, "auto_renew": {"type": "bool", "default": True}, "default_ha_mirror_queue": {"type": "bool", "default": False}, "bandwidth": {"type": "int"}, "public_access": {"type": "bool", "default": False}, "deletion_protection": {"type": "bool"}, "remark": {}, "tags": {"type": "dict"}, "international": {"type": "bool", "default": False}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("instance_id", "name")], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, instance=None)
            if current.get("EnableDeletionProtection") and p.get("deletion_protection") is not False: module.fail_json(msg="set deletion_protection=false to authorize disabling protection before deletion")
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                if current.get("EnableDeletionProtection"): module.sdk_call(client.ModifyRabbitMQVipInstance, modify_request(models, p, current["InstanceId"]))
                module.sdk_call(client.DeleteRabbitMQVipInstance, delete_request(models, current["InstanceId"], p["international"]))
            module.exit_json(changed=True, **(diff or {}), instance=None)
        if not current:
            missing = [k for k in ("name", "zone_ids", "vpc_id", "subnet_id") if p.get(k) is None]
            if missing: module.fail_json(msg="creation parameters are required for a new RabbitMQ instance", missing=missing)
            target = {"InstanceName": p["name"], "InstanceVersion": p.get("cluster_version") or "3.11.8", "NodeCount": p.get("node_count") or (3 if len(p["zone_ids"]) > 1 else 1), "MaxStorage": p["storage_size"], "EnableDeletionProtection": bool(p.get("deletion_protection"))}; diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["instance_id"] = module.sdk_call(client.CreateRabbitMQVipInstance, create_request(models, p)).InstanceId; _wait(module, client, models, p, [1]); current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else target)
        vpcs = current.get("Vpcs") or []; actual_vpcs = {(x.get("VpcId"), x.get("SubnetId")) for x in vpcs}; drift = {}
        if p.get("vpc_id") and (p["vpc_id"], p.get("subnet_id")) not in actual_vpcs: drift["Vpc"] = (sorted(actual_vpcs), (p["vpc_id"], p.get("subnet_id")))
        if p.get("cluster_version") and current.get("InstanceVersion") != p["cluster_version"]: drift["InstanceVersion"] = (current.get("InstanceVersion"), p["cluster_version"])
        if p.get("node_count") is not None and current.get("NodeCount") != p["node_count"]: drift["NodeCount"] = (current.get("NodeCount"), p["node_count"])
        if drift: module.fail_json(msg="RabbitMQ network, version and node topology are immutable", immutable_drift=drift)
        desired = {"InstanceName": p.get("name") or current.get("InstanceName"), "Remark": p.get("remark") if p.get("remark") is not None else current.get("Remark"), "EnableDeletionProtection": p.get("deletion_protection") if p.get("deletion_protection") is not None else current.get("EnableDeletionProtection"), "Tags": p.get("tags") if p.get("tags") is not None else _tag_map(current)}; before = {"InstanceName": current.get("InstanceName"), "Remark": current.get("Remark"), "EnableDeletionProtection": current.get("EnableDeletionProtection"), "Tags": _tag_map(current)}
        if before == desired: module.exit_json(changed=False, instance=current)
        diff = maybe_diff(module, before, desired)
        if not module.check_mode: module.sdk_call(client.ModifyRabbitMQVipInstance, modify_request(models, p, current["InstanceId"])); p["instance_id"] = current["InstanceId"]; _wait(module, client, models, p, [1]); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), instance=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
