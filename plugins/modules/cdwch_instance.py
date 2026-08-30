#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cdwch_instance
short_description: Manage Tencent Cloud TCHouse-C instances
version_added: "0.14.0"
description: Creates and destroys TCHouse-C instances and reconciles ClickHouse and ZooKeeper node count, specification and disk capacity.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing instance ID.}
  name: {type: str, description: Instance name; immutable after creation.}
  zone: {type: str, description: Primary availability zone; immutable after creation.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  product_version: {type: str, description: TCHouse-C version; immutable after creation.}
  high_availability: {type: bool, description: Enable ClickHouse high availability during creation.}
  zk_high_availability: {type: bool, description: Enable ZooKeeper high availability during creation.}
  data_spec_name: {type: str, description: ClickHouse node specification.}
  data_node_count: {type: int, description: Desired ClickHouse node count.}
  data_disk_size: {type: int, description: Desired ClickHouse disk size in GiB; expansion only.}
  common_spec_name: {type: str, description: ZooKeeper node specification.}
  common_node_count: {type: int, description: Desired ZooKeeper node count.}
  common_disk_size: {type: int, description: Desired ZooKeeper disk size in GiB; expansion only.}
  charge_type: {type: str, choices: [PREPAID, POSTPAID_BY_HOUR], description: Billing mode; defaults to POSTPAID_BY_HOUR during creation.}
  period_months: {type: int, default: 1, description: Prepaid purchase period.}
  auto_renew: {type: bool, default: false, description: Prepaid auto-renewal during creation.}
  password: {type: str, description: Initial default-user password.}
  tags: {type: dict, description: Creation-time tags; immutable because the product API exposes no tag update endpoint.}
  cls_logset_id: {type: str, description: Initial CLS logset ID.}
  cos_bucket_name: {type: str, description: Initial COS bucket name.}
  mount_disk_type: {type: int, choices: [0, 1, 2], description: "No mount, raw disk or LVM mount mode."}
  secondary_zones:
    type: list
    elements: dict
    description: Creation-time secondary availability zones.
    suboptions:
      zone: {type: str, required: true, description: Secondary availability zone.}
      subnet_id: {type: str, required: true, description: Secondary-zone subnet ID.}
      user_ip_count: {type: int, description: Available subnet IP count.}
  scale_out_cluster: {type: str, description: Virtual cluster receiving newly added ClickHouse nodes.}
  user_subnet_ip_count: {type: int, description: Remaining subnet IP count required by scale-out.}
  scale_out_node_ip: {type: str, description: Metadata synchronization node IP required by scale-out.}
  reduce_shard_info: {type: list, elements: str, description: Shard IP groups required by scale-in.}
  allow_scale_in: {type: bool, default: false, description: Explicitly authorize reducing data or common node count.}
  rolling_spec_change: {type: bool, default: true, description: Use rolling restart for specification changes.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cdwch_instance:
    name: production-clickhouse
    zone: ap-beijing-2
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    product_version: 23.8.9.1
    data_spec_name: S_16_64_H
    data_node_count: 2
    data_disk_size: 200
    common_spec_name: S_4_16_H
    common_node_count: 3
    common_disk_size: 100
    password: "{{ vault_clickhouse_password }}"
'''
RETURN = r'''instance: {description: Effective TCHouse-C instance metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.cdwch.v20200915 import models, cdwch_client
    return models, cdwch_client
def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.Tag(); item.TagKey, item.TagValue = key, value; result.append(item)
    return result
def _spec(models, name, count, disk):
    if name is None and count is None and disk is None: return None
    item = models.NodeSpec(); item.SpecName, item.Count, item.DiskSize = name, count, disk; return item
def _secondary_zones(models, values):
    result = []
    for value in values or []:
        item = models.SecondaryZoneInfo(); item.SecondaryZone, item.SecondarySubnet = value["zone"], value["subnet_id"]; item.UserIpNum, item.SecondaryUserSubnetIPNum = str(value.get("user_ip_count")) if value.get("user_ip_count") is not None else None, value.get("user_ip_count"); result.append(item)
    return result
def describe_request(models, p, offset=0):
    r = models.DescribeInstancesNewRequest(); r.Offset, r.Limit, r.IsSimple = offset, 100, False; r.SearchInstanceId = p.get("instance_id"); r.SearchInstanceName = p.get("name") if not p.get("instance_id") else None; return r
def detail_request(models, instance_id):
    r = models.DescribeInstanceRequest(); r.InstanceId, r.IsOpenApi = instance_id, True; return r
def create_request(models, p):
    r = models.CreateInstanceNewRequest(); r.Zone, r.HaFlag, r.UserVPCId, r.UserSubnetId = p["zone"], bool(p.get("high_availability")), p["vpc_id"], p["subnet_id"]; r.ProductVersion, r.InstanceName = p["product_version"], p["name"]
    r.ChargeProperties = models.Charge(); r.ChargeProperties.ChargeType = p.get("charge_type") or "POSTPAID_BY_HOUR"; r.ChargeProperties.RenewFlag, r.ChargeProperties.TimeSpan = 1 if p["auto_renew"] else 0, p["period_months"]
    r.DataSpec = _spec(models, p["data_spec_name"], p["data_node_count"], p["data_disk_size"]); r.CommonSpec = _spec(models, p.get("common_spec_name"), p.get("common_node_count"), p.get("common_disk_size"))
    r.TagItems, r.ClsLogSetId, r.CosBucketName = _tags(models, p.get("tags")), p.get("cls_logset_id"), p.get("cos_bucket_name"); r.MountDiskType, r.HAZk = p.get("mount_disk_type"), p.get("zk_high_availability"); r.SecondaryZoneInfo, r.CkDefaultUserPwd = _secondary_zones(models, p.get("secondary_zones")), p["password"]; return r
def destroy_request(models, instance_id):
    r = models.DestroyInstanceRequest(); r.InstanceId = instance_id; return r
def scale_nodes_request(models, p, instance_id, node_type, count):
    r = models.ScaleOutInstanceRequest(); r.InstanceId, r.Type, r.NodeCount = instance_id, node_type, count; r.ScaleOutCluster, r.UserSubnetIPNum, r.ScaleOutNodeIp = p.get("scale_out_cluster"), p.get("user_subnet_ip_count"), p.get("scale_out_node_ip"); r.ReduceShardInfo = p.get("reduce_shard_info"); return r
def scale_spec_request(models, instance_id, node_type, spec_name, rolling=True):
    r = models.ScaleUpInstanceRequest(); r.InstanceId, r.Type, r.SpecName, r.ScaleUpEnableRolling = instance_id, node_type, spec_name, rolling; return r
def resize_disk_request(models, instance_id, node_type, size):
    r = models.ResizeDiskRequest(); r.InstanceId, r.Type, r.DiskSize = instance_id, node_type, size; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeInstancesNew, describe_request(models, p)); matches = []
    for item in response.InstancesList or []:
        value = item._serialize(allow_none=True)
        if (p.get("instance_id") and value.get("InstanceId") == p["instance_id"]) or (not p.get("instance_id") and value.get("InstanceName") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple TCHouse-C instances matched; specify instance_id")
    if matches:
        response = module.sdk_call(client.DescribeInstance, detail_request(models, matches[0]["InstanceId"])); detail = response.InstanceInfo._serialize(allow_none=True) if response.InstanceInfo else {}; matches[0].update(detail)
    return matches[0] if matches else None
def _wait(module, client, models, p, predicate, label):
    def poll():
        current = find(module, client, models, p)
        if current is None: return "READY" if predicate(None) else "ABSENT"
        state = str(current.get("Status", ""))
        flow = current.get("InstanceStateInfo") or {}
        if state.lower() in ("failed", "error") or (flow.get("FlowMsg") and "fail" in str(flow.get("FlowMsg")).lower()): module.fail_json(msg="TCHouse-C asynchronous operation failed", operation=label, instance=current)
        return "READY" if state in ("Serving", "Deleted") and predicate(current) else state
    wait_for_state(module, poll, ["READY"], timeout=module.params["waiter_timeout"], delay=module.params["waiter_delay"])
def _tag_dict(values): return {item.get("TagKey"): item.get("TagValue") for item in values or []}


def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {}, "name": {}, "zone": {}, "vpc_id": {}, "subnet_id": {}, "product_version": {}, "high_availability": {"type": "bool"}, "zk_high_availability": {"type": "bool"}, "data_spec_name": {}, "data_node_count": {"type": "int"}, "data_disk_size": {"type": "int"}, "common_spec_name": {}, "common_node_count": {"type": "int"}, "common_disk_size": {"type": "int"}, "charge_type": {"choices": ["PREPAID", "POSTPAID_BY_HOUR"]}, "period_months": {"type": "int", "default": 1}, "auto_renew": {"type": "bool", "default": False}, "password": {"no_log": True}, "tags": {"type": "dict"}, "cls_logset_id": {}, "cos_bucket_name": {}, "mount_disk_type": {"type": "int", "choices": [0, 1, 2]}, "secondary_zones": {"type": "list", "elements": "dict", "options": {"zone": {"required": True}, "subnet_id": {"required": True}, "user_ip_count": {"type": "int"}}}, "scale_out_cluster": {}, "user_subnet_ip_count": {"type": "int"}, "scale_out_node_ip": {}, "reduce_shard_info": {"type": "list", "elements": "str"}, "allow_scale_in": {"type": "bool", "default": False}, "rolling_spec_change": {"type": "bool", "default": True}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("instance_id", "name")], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CdwchClient, "cdwch.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, instance=None)
            diff = maybe_diff(module, current, None); instance_id = current["InstanceId"]
            if not module.check_mode: module.sdk_call(client.DestroyInstance, destroy_request(models, instance_id)); p["instance_id"] = instance_id; _wait(module, client, models, p, lambda value: value is None or value.get("Status") == "Deleted", "destroy")
            module.exit_json(changed=True, **(diff or {}), instance=None)
        if not current:
            missing = [key for key in ("name", "zone", "vpc_id", "subnet_id", "product_version", "data_spec_name", "data_node_count", "data_disk_size", "password") if p.get(key) is None]
            if missing: module.fail_json(msg="creation parameters are required for a new TCHouse-C instance", missing=missing)
            target = {"InstanceName": p["name"], "Zone": p["zone"], "VpcId": p["vpc_id"], "SubnetId": p["subnet_id"], "Version": p["product_version"], "MasterSummary": {"Spec": p["data_spec_name"], "NodeSize": p["data_node_count"], "Disk": p["data_disk_size"]}}; diff = maybe_diff(module, None, target)
            if not module.check_mode:
                response = module.sdk_call(client.CreateInstanceNew, create_request(models, p)); p["instance_id"] = response.InstanceId; _wait(module, client, models, p, lambda value: value is not None, "create"); current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else target)
        master, common = current.get("MasterSummary") or {}, current.get("CommonSummary") or {}; current_pay = str(current.get("PayMode", "")).lower(); wanted_pay = {"PREPAID": "prepay", "POSTPAID_BY_HOUR": "hour"}.get(p.get("charge_type"))
        immutable = {"InstanceName": p.get("name"), "Zone": p.get("zone"), "VpcId": p.get("vpc_id"), "SubnetId": p.get("subnet_id"), "Version": p.get("product_version"), "HA": str(p["high_availability"]).lower() if p.get("high_availability") is not None else None, "HAZk": p.get("zk_high_availability"), "PayMode": wanted_pay, "Tags": p.get("tags")}; observed = {"InstanceName": current.get("InstanceName"), "Zone": current.get("Zone"), "VpcId": current.get("VpcId"), "SubnetId": current.get("SubnetId"), "Version": current.get("Version"), "HA": str(current.get("HA", "")).lower(), "HAZk": current.get("HAZk"), "PayMode": current_pay, "Tags": _tag_dict(current.get("Tags"))}; drift = {key: (observed.get(key), value) for key, value in immutable.items() if value is not None and observed.get(key) != value}
        if drift: module.fail_json(msg="TCHouse-C identity, placement, version, billing, HA and tags are immutable", immutable_drift=drift)
        before = {"DataSpec": master.get("Spec"), "DataCount": master.get("NodeSize"), "DataDisk": master.get("Disk"), "CommonSpec": common.get("Spec"), "CommonCount": common.get("NodeSize"), "CommonDisk": common.get("Disk")}; desired = {"DataSpec": p.get("data_spec_name") or before["DataSpec"], "DataCount": p.get("data_node_count") if p.get("data_node_count") is not None else before["DataCount"], "DataDisk": p.get("data_disk_size") if p.get("data_disk_size") is not None else before["DataDisk"], "CommonSpec": p.get("common_spec_name") or before["CommonSpec"], "CommonCount": p.get("common_node_count") if p.get("common_node_count") is not None else before["CommonCount"], "CommonDisk": p.get("common_disk_size") if p.get("common_disk_size") is not None else before["CommonDisk"]}
        for key in ("DataDisk", "CommonDisk"):
            if desired[key] is not None and before[key] is not None and desired[key] < before[key]: module.fail_json(msg="TCHouse-C disks cannot be reduced", field=key)
        shrinking = any(desired[key] is not None and before[key] is not None and desired[key] < before[key] for key in ("DataCount", "CommonCount"))
        if shrinking and not p["allow_scale_in"]: module.fail_json(msg="set allow_scale_in=true to authorize reducing TCHouse-C node count")
        if shrinking and not p.get("reduce_shard_info"): module.fail_json(msg="reduce_shard_info is required for TCHouse-C scale-in")
        growing = any(desired[key] is not None and before[key] is not None and desired[key] > before[key] for key in ("DataCount", "CommonCount"))
        if growing and (p.get("user_subnet_ip_count") is None or not p.get("scale_out_node_ip")): module.fail_json(msg="user_subnet_ip_count and scale_out_node_ip are required for TCHouse-C scale-out")
        if before == desired: module.exit_json(changed=False, instance=current)
        diff = maybe_diff(module, before, desired); instance_id = current["InstanceId"]
        if not module.check_mode:
            for prefix, node_type, summary_key in (("Data", "DATA", "MasterSummary"), ("Common", "COMMON", "CommonSummary")):
                if before[prefix + "Spec"] != desired[prefix + "Spec"]:
                    module.sdk_call(client.ScaleUpInstance, scale_spec_request(models, instance_id, node_type, desired[prefix + "Spec"], p["rolling_spec_change"])); _wait(module, client, models, p, lambda value, k=summary_key, target=desired[prefix + "Spec"]: (value.get(k) or {}).get("Spec") == target, "scale specification")
                if before[prefix + "Disk"] != desired[prefix + "Disk"]:
                    module.sdk_call(client.ResizeDisk, resize_disk_request(models, instance_id, node_type, desired[prefix + "Disk"])); _wait(module, client, models, p, lambda value, k=summary_key, target=desired[prefix + "Disk"]: (value.get(k) or {}).get("Disk") == target, "resize disk")
                if before[prefix + "Count"] != desired[prefix + "Count"]:
                    module.sdk_call(client.ScaleOutInstance, scale_nodes_request(models, p, instance_id, node_type, desired[prefix + "Count"])); _wait(module, client, models, p, lambda value, k=summary_key, target=desired[prefix + "Count"]: (value.get(k) or {}).get("NodeSize") == target, "scale nodes")
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), instance=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
