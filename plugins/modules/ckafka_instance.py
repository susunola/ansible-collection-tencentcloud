#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: ckafka_instance
short_description: Manage Tencent Cloud CKafka instances
version_added: "0.14.0"
description: Creates prepaid or postpaid CKafka instances, reconciles runtime attributes and prepaid capacity, and deletes instances.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing CKafka instance ID.}
  name: {type: str, description: Instance name.}
  zones: {type: list, elements: int, description: Numeric availability-zone IDs; immutable after creation.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  charge_type: {type: str, choices: [PREPAID, POSTPAID_BY_HOUR], default: POSTPAID_BY_HOUR, description: Billing mode.}
  period_months: {type: int, default: 1, description: Prepaid purchase period.}
  auto_renew: {type: bool, default: false, description: Automatically renew prepaid instances.}
  instance_type: {type: int, description: Numeric instance type used during creation.}
  specification: {type: str, description: Sales specification type.}
  kafka_version: {type: str, description: Kafka version; immutable after creation.}
  disk_type: {type: str, description: Disk type; immutable after creation.}
  disk_size: {type: int, description: Disk capacity in GiB.}
  bandwidth: {type: int, description: Peak bandwidth in MB per second.}
  partitions: {type: int, description: Partition capacity.}
  topic_count: {type: int, description: Topic capacity for postpaid creation.}
  retention_minutes: {type: int, description: Message retention period in minutes.}
  max_message_bytes: {type: int, description: Maximum message size in bytes.}
  retention_bytes: {type: int, description: Maximum retained bytes per partition.}
  unclean_leader_election: {type: bool, description: Permit unclean leader election.}
  deletion_protection: {type: bool, description: Protect the instance from deletion.}
  tags: {type: dict, default: {}, description: Tags applied during creation.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.ckafka_instance:
    name: production-kafka
    zones: [100003]
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    instance_type: 1
    specification: profession
    kafka_version: '2.8.1'
    disk_type: CLOUD_BASIC
    disk_size: 500
    bandwidth: 40
    partitions: 400
'''
RETURN = r'''instance: {description: Effective CKafka instance attributes., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.ckafka.v20190819 import models, ckafka_client
    return models, ckafka_client
def list_request(models, p, offset=0):
    r = models.DescribeInstancesDetailRequest(); r.Offset, r.Limit = offset, 100
    r.InstanceIdList = [p["instance_id"]] if p.get("instance_id") else None
    if not p.get("instance_id") and p.get("name"):
        f = models.Filter(); f.Name, f.Values = "instance-name", [p["name"]]; r.Filters = [f]
    return r
def attributes_request(models, instance_id):
    r = models.DescribeInstanceAttributesRequest(); r.InstanceId = instance_id; return r
def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.Tag(); item.TagKey, item.TagValue = key, value; result.append(item)
    return result
def create_prepaid_request(models, p):
    r = models.CreateInstancePreRequest(); r.InstanceName, r.ZoneId = p["name"], p["zones"][0]
    r.ZoneIds, r.MultiZoneFlag = p["zones"], len(p["zones"]) > 1; r.Period, r.RenewFlag = str(p["period_months"]), 1 if p["auto_renew"] else 0
    r.InstanceType, r.SpecificationsType, r.KafkaVersion = p["instance_type"], p["specification"], p["kafka_version"]
    r.VpcId, r.SubnetId, r.MsgRetentionTime = p["vpc_id"], p["subnet_id"], p["retention_minutes"]
    r.DiskType, r.DiskSize, r.BandWidth, r.Partition = p["disk_type"], p["disk_size"], p["bandwidth"], p["partitions"]
    r.InstanceNum, r.Tags = 1, _tags(models, p["tags"]); return r
def create_postpaid_request(models, p):
    r = models.CreatePostPaidInstanceRequest(); r.InstanceName, r.ZoneId = p["name"], p["zones"][0]
    r.ZoneIds, r.MultiZoneFlag = p["zones"], len(p["zones"]) > 1
    r.InstanceType, r.SpecificationsType, r.KafkaVersion = p["instance_type"], p["specification"], p["kafka_version"]
    r.VpcId, r.SubnetId, r.MsgRetentionTime = p["vpc_id"], p["subnet_id"], p["retention_minutes"]
    r.DiskType, r.DiskSize, r.BandWidth, r.Partition, r.TopicNum = p["disk_type"], p["disk_size"], p["bandwidth"], p["partitions"], p.get("topic_count")
    r.InstanceNum, r.Tags = 1, _tags(models, p["tags"]); return r
def modify_request(models, p, instance_id):
    r = models.ModifyInstanceAttributesRequest(); r.InstanceId, r.InstanceName = instance_id, p.get("name")
    r.MsgRetentionTime, r.MaxMessageByte, r.RetentionBytes = p.get("retention_minutes"), p.get("max_message_bytes"), p.get("retention_bytes")
    r.UncleanLeaderElectionEnable = None if p.get("unclean_leader_election") is None else int(p["unclean_leader_election"])
    r.DeleteProtectionEnable = None if p.get("deletion_protection") is None else int(p["deletion_protection"]); return r
def resize_request(models, p, instance_id):
    r = models.ModifyInstancePreRequest(); r.InstanceId, r.DiskSize, r.BandWidth, r.Partition = instance_id, p.get("disk_size"), p.get("bandwidth"), p.get("partitions"); return r
def delete_prepaid_request(models, instance_id):
    r = models.DeleteInstancePreRequest(); r.InstanceId = instance_id; return r
def delete_postpaid_request(models, instance_id):
    r = models.DeleteInstancePostRequest(); r.InstanceId = instance_id; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeInstancesDetail, list_request(models, p)); result = response.Result
    matches = []
    for item in (result.InstanceList if result else []) or []:
        value = item._serialize(allow_none=True)
        if (p.get("instance_id") and value.get("InstanceId") == p["instance_id"]) or (not p.get("instance_id") and value.get("InstanceName") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple CKafka instances matched; specify instance_id")
    if not matches: return None
    return module.sdk_call(client.DescribeInstanceAttributes, attributes_request(models, matches[0]["InstanceId"])).Result._serialize(allow_none=True)
def _wait(module, client, models, p, states):
    wait_for_state(module, lambda: (find(module, client, models, p) or {}).get("Status"), states, timeout=module.params["waiter_timeout"], delay=module.params["waiter_delay"])


def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {}, "name": {}, "zones": {"type": "list", "elements": "int"}, "vpc_id": {}, "subnet_id": {}, "charge_type": {"choices": ["PREPAID", "POSTPAID_BY_HOUR"], "default": "POSTPAID_BY_HOUR"}, "period_months": {"type": "int", "default": 1}, "auto_renew": {"type": "bool", "default": False}, "instance_type": {"type": "int"}, "specification": {}, "kafka_version": {}, "disk_type": {}, "disk_size": {"type": "int"}, "bandwidth": {"type": "int"}, "partitions": {"type": "int"}, "topic_count": {"type": "int"}, "retention_minutes": {"type": "int"}, "max_message_bytes": {"type": "int"}, "retention_bytes": {"type": "int"}, "unclean_leader_election": {"type": "bool"}, "deletion_protection": {"type": "bool"}, "tags": {"type": "dict", "default": {}}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("instance_id", "name")], supports_check_mode=True); p = module.params
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CkafkaClient, "ckafka.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, instance=None)
            diff = maybe_diff(module, current, None); request = delete_prepaid_request(models, current["InstanceId"]) if str(current.get("InstanceChargeType", "")).upper() == "PREPAID" else delete_postpaid_request(models, current["InstanceId"])
            if not module.check_mode: module.sdk_call(client.DeleteInstancePre if request.__class__.__name__.endswith("PreRequest") else client.DeleteInstancePost, request)
            module.exit_json(changed=True, **(diff or {}), instance=None)
        if not current:
            required = ("name", "zones", "vpc_id", "subnet_id", "instance_type", "specification", "kafka_version", "disk_type", "disk_size", "bandwidth", "partitions", "retention_minutes"); missing = [k for k in required if p.get(k) is None]
            if missing: module.fail_json(msg="creation parameters are required for a new CKafka instance", missing=missing)
            target = {"InstanceName": p["name"], "ZoneIds": p["zones"], "VpcId": p["vpc_id"], "SubnetId": p["subnet_id"], "DiskSize": p["disk_size"], "Bandwidth": p["bandwidth"], "PartitionNumber": p["partitions"]}; diff = maybe_diff(module, None, target)
            if not module.check_mode:
                request = create_prepaid_request(models, p) if p["charge_type"] == "PREPAID" else create_postpaid_request(models, p); response = module.sdk_call(client.CreateInstancePre if p["charge_type"] == "PREPAID" else client.CreatePostPaidInstance, request)
                data = response.Result.Data if response.Result else None
                if data and data.InstanceId: p["instance_id"] = data.InstanceId
                _wait(module, client, models, p, [1]); current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else target)
        immutable = {"VpcId": p.get("vpc_id"), "SubnetId": p.get("subnet_id"), "Version": p.get("kafka_version")}; drift = {k: (current.get(k), v) for k, v in immutable.items() if v is not None and current.get(k) != v}
        if p.get("zones") and sorted(current.get("ZoneIds") or [current.get("ZoneId")]) != sorted(p["zones"]): drift["ZoneIds"] = (current.get("ZoneIds"), p["zones"])
        if drift: module.fail_json(msg="CKafka placement and Kafka version are immutable", immutable_drift=drift)
        mapping = {"InstanceName": "name", "MsgRetentionTime": "retention_minutes", "MaxMessageByte": "max_message_bytes", "RetentionBytes": "retention_bytes", "UncleanLeaderElectionEnable": "unclean_leader_election", "DeleteProtectionEnable": "deletion_protection", "DiskSize": "disk_size", "Bandwidth": "bandwidth", "PartitionNumber": "partitions"}
        desired = {field: p[param] if p.get(param) is not None else current.get(field) for field, param in mapping.items()}; before = {field: current.get(field) for field in desired}
        if before == desired: module.exit_json(changed=False, instance=current)
        diff = maybe_diff(module, before, desired); instance_id = current["InstanceId"]
        if not module.check_mode:
            attrs = ("InstanceName", "MsgRetentionTime", "MaxMessageByte", "RetentionBytes", "UncleanLeaderElectionEnable", "DeleteProtectionEnable")
            if any(before[k] != desired[k] for k in attrs): module.sdk_call(client.ModifyInstanceAttributes, modify_request(models, p, instance_id))
            capacity = ("DiskSize", "Bandwidth", "PartitionNumber")
            if any(before[k] != desired[k] for k in capacity):
                if str(current.get("InstanceChargeType", "")).upper() != "PREPAID": module.fail_json(msg="CKafka capacity modification is only exposed by the SDK for prepaid instances")
                module.sdk_call(client.ModifyInstancePre, resize_request(models, p, instance_id))
            p["instance_id"] = instance_id; _wait(module, client, models, p, [1]); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), instance=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
