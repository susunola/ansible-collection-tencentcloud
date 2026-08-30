#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: mqtt_instance
short_description: Manage Tencent Cloud MQTT instances
version_added: "0.14.0"
description: Creates, updates and deletes MQTT instances with explicit creation-only network and billing settings.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing MQTT instance ID.}
  name: {type: str, description: Instance name.}
  instance_type: {type: str, choices: [BASIC, PRO, PLATINUM], description: Instance edition; required for creation.}
  sku_code: {type: str, description: Product SKU; required for creation and mutable within supported edition boundaries.}
  remark: {type: str, default: '', description: Instance remark.}
  vpcs: {type: list, elements: dict, suboptions: {vpc_id: {type: str, required: true, description: VPC ID.}, subnet_id: {type: str, required: true, description: Subnet ID.}}, description: Creation-only VPC and subnet bindings.}
  enable_public: {type: bool, default: false, description: Enable public access during creation.}
  bandwidth: {type: int, description: Public bandwidth in Mbps.}
  ip_rules: {type: list, elements: dict, suboptions: {ip: {type: str, required: true, description: IP address or CIDR.}, allow: {type: bool, default: true, description: Allow matching traffic.}, remark: {type: str, default: '', description: Rule remark.}}, description: Creation-time public IP rules.}
  tags: {type: dict, description: Creation-time tags.}
  pay_mode: {type: int, choices: [0, 1], default: 0, description: Postpaid or prepaid billing.}
  period_months: {type: int, default: 1, description: Prepaid purchase period.}
  auto_renew: {type: bool, default: true, description: Prepaid automatic renewal.}
  authorization_policy: {type: bool, description: Enable authorization policies.}
  message_rate: {type: int, description: Per-client message rate limit.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.mqtt_instance:
    name: production-mqtt
    instance_type: PRO
    sku_code: pro_2k
    vpcs: [{vpc_id: vpc-xxxxxxxx, subnet_id: subnet-xxxxxxxx}]
'''
RETURN = r'''instance: {description: Effective MQTT instance metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.mqtt.v20240516 import models, mqtt_client
    return models, mqtt_client
def list_request(models):
    r = models.DescribeInstanceListRequest(); r.Offset, r.Limit = 0, 100; return r
def describe_request(models, instance_id):
    r = models.DescribeInstanceRequest(); r.InstanceId = instance_id; return r
def _items(models, cls, values):
    result = []
    for value in values or []:
        x = cls()
        for key, item in value.items(): setattr(x, "".join(part.capitalize() for part in key.split("_")), item)
        result.append(x)
    return result
def create_request(models, p):
    r = models.CreateInstanceRequest(); r.InstanceType, r.Name, r.SkuCode, r.Remark = p["instance_type"], p["name"], p["sku_code"], p["remark"]; r.VpcList = _items(models, models.VpcInfo, p.get("vpcs")); r.IpRules = _items(models, models.IpRule, p.get("ip_rules")); r.EnablePublic, r.Bandwidth = p["enable_public"], p.get("bandwidth"); r.PayMode, r.TimeSpan, r.RenewFlag = p["pay_mode"], p["period_months"], 1 if p["auto_renew"] else 0
    r.TagList = []
    for key, value in sorted((p.get("tags") or {}).items()): t = models.Tag(); t.TagKey, t.TagValue = key, value; r.TagList.append(t)
    return r
def update_request(models, p, current):
    r = models.ModifyInstanceRequest(); r.InstanceId = current["InstanceId"]; r.Name, r.Remark = p.get("name") or current.get("InstanceName"), p["remark"]; r.SkuCode = p.get("sku_code") or current.get("SkuCode"); r.AuthorizationPolicy, r.MessageRate = p.get("authorization_policy"), p.get("message_rate"); return r
def delete_request(models, instance_id):
    r = models.DeleteInstanceRequest(); r.InstanceId = instance_id; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeInstanceList, list_request(models)); matches = []
    for item in response.Data or []:
        value = item._serialize(allow_none=True)
        if (p.get("instance_id") and value.get("InstanceId") == p["instance_id"]) or (not p.get("instance_id") and value.get("InstanceName") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple MQTT instances matched; specify instance_id")
    if not matches: return None
    value = module.sdk_call(client.DescribeInstance, describe_request(models, matches[0]["InstanceId"]))._serialize(allow_none=True); value.pop("RequestId", None); return value
def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {}, "name": {}, "instance_type": {"choices": ["BASIC", "PRO", "PLATINUM"]}, "sku_code": {}, "remark": {"default": ""}, "vpcs": {"type": "list", "elements": "dict", "options": {"vpc_id": {"required": True}, "subnet_id": {"required": True}}}, "enable_public": {"type": "bool", "default": False}, "bandwidth": {"type": "int"}, "ip_rules": {"type": "list", "elements": "dict", "options": {"ip": {"required": True}, "allow": {"type": "bool", "default": True}, "remark": {"default": ""}}}, "tags": {"type": "dict"}, "pay_mode": {"type": "int", "choices": [0, 1], "default": 0}, "period_months": {"type": "int", "default": 1}, "auto_renew": {"type": "bool", "default": True}, "authorization_policy": {"type": "bool"}, "message_rate": {"type": "int"}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("instance_id", "name")], required_if=[("enable_public", True, ["bandwidth"])], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.MqttClient, "mqtt.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, instance=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteInstance, delete_request(models, current["InstanceId"]))
            module.exit_json(changed=True, **(diff or {}), instance=None)
        if not current:
            missing = [k for k in ("name", "instance_type", "sku_code", "vpcs") if not p.get(k)]
            if missing: module.fail_json(msg="creation parameters are required for a new MQTT instance", missing=missing)
            target = {"InstanceName": p["name"], "InstanceType": p["instance_type"], "SkuCode": p["sku_code"], "Remark": p["remark"]}; diff = maybe_diff(module, None, target)
            if not module.check_mode: p["instance_id"] = module.sdk_call(client.CreateInstance, create_request(models, p)).InstanceId; current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else target)
        if p.get("instance_type") and current.get("InstanceType") != p["instance_type"]: module.fail_json(msg="MQTT instance_type is immutable", before=current.get("InstanceType"), after=p["instance_type"])
        before = {"InstanceName": current.get("InstanceName"), "Remark": current.get("Remark") or "", "SkuCode": current.get("SkuCode"), "AuthorizationPolicy": current.get("AuthorizationPolicy"), "MessageRate": current.get("MessageRate")}; target = {"InstanceName": p.get("name") or before["InstanceName"], "Remark": p["remark"], "SkuCode": p.get("sku_code") or before["SkuCode"], "AuthorizationPolicy": p.get("authorization_policy") if p.get("authorization_policy") is not None else before["AuthorizationPolicy"], "MessageRate": p.get("message_rate") if p.get("message_rate") is not None else before["MessageRate"]}
        if before == target: module.exit_json(changed=False, instance=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode: module.sdk_call(client.ModifyInstance, update_request(models, p, current)); p["instance_id"] = current["InstanceId"]; current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), instance=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__ == "__main__": main()
