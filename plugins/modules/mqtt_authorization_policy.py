#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: mqtt_authorization_policy
short_description: Manage Tencent Cloud MQTT authorization policies
version_added: "0.14.0"
description: Creates, updates and deletes data-plane authorization policies for MQTT instances.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: MQTT instance ID.}
  policy_id: {type: int, description: Existing policy ID.}
  name: {type: str, description: Policy name.}
  priority: {type: int, description: Unique policy priority; lower values run first.}
  effect: {type: str, choices: [allow, deny], description: Allow or deny decision.}
  actions: {type: list, elements: str, choices: [connect, pub, sub], description: MQTT operations.}
  resources: {type: list, elements: str, description: Topic resource patterns.}
  username: {type: str, default: '', description: Optional username condition.}
  client_id: {type: str, default: '', description: Optional client ID condition.}
  ip: {type: str, default: '', description: Optional IP or CIDR condition.}
  retain: {type: int, choices: [1, 2, 3], description: Retained-message match mode.}
  qos: {type: list, elements: int, choices: [0, 1, 2], description: Matching QoS values.}
  remark: {type: str, default: '', description: Policy remark.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.mqtt_authorization_policy:
    instance_id: mqtt-xxxxxxxx
    name: application-publish
    priority: 10
    effect: allow
    actions: [connect, pub]
    resources: [orders/#]
'''
RETURN = r'''policy: {description: Effective MQTT authorization policy., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.mqtt.v20240516 import models, mqtt_client
    return models, mqtt_client
def describe_request(models, p):
    r = models.DescribeAuthorizationPoliciesRequest(); r.InstanceId = p["instance_id"]; return r
def _csv(values): return ",".join(str(x) for x in (values or []))
def create_request(models, p):
    r = models.CreateAuthorizationPolicyRequest(); r.InstanceId, r.PolicyName, r.PolicyVersion = p["instance_id"], p["name"], 1; r.Priority, r.Effect = p["priority"], p["effect"]; r.Actions, r.Resources, r.Qos = _csv(p["actions"]), _csv(p["resources"]), _csv(p.get("qos")); r.Username, r.ClientId, r.Ip, r.Retain, r.Remark = p["username"], p["client_id"], p["ip"], p.get("retain"), p["remark"]; return r
def update_request(models, p, policy_id):
    r = models.ModifyAuthorizationPolicyRequest(); r.Id, r.InstanceId, r.PolicyName, r.PolicyVersion = policy_id, p["instance_id"], p["name"], 1; r.Priority, r.Effect = p["priority"], p["effect"]; r.Actions, r.Resources, r.Qos = _csv(p["actions"]), _csv(p["resources"]), _csv(p.get("qos")); r.Username, r.ClientId, r.Ip, r.Retain, r.Remark = p["username"], p["client_id"], p["ip"], p.get("retain"), p["remark"]; return r
def delete_request(models, p, policy_id):
    r = models.DeleteAuthorizationPolicyRequest(); r.InstanceId, r.Id = p["instance_id"], policy_id; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeAuthorizationPolicies, describe_request(models, p)); matches = []
    for item in response.Data or []:
        value = item._serialize(allow_none=True)
        if (p.get("policy_id") is not None and value.get("Id") == p["policy_id"]) or (p.get("policy_id") is None and value.get("PolicyName") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple MQTT authorization policies matched; specify policy_id")
    return matches[0] if matches else None
def comparable(v):
    def split(x): return sorted(y for y in (x or "").split(",") if y != "")
    return {"PolicyName": v.get("PolicyName"), "Priority": v.get("Priority"), "Effect": v.get("Effect"), "Actions": split(v.get("Actions")), "Resources": split(v.get("Resources")), "Username": v.get("Username") or "", "ClientId": v.get("ClientId") or "", "Ip": v.get("Ip") or "", "Retain": v.get("Retain"), "Qos": split(v.get("Qos")), "Remark": v.get("Remark") or ""}
def desired(p, current=None):
    old = comparable(current) if current else {}; return {"PolicyName": p.get("name") or old.get("PolicyName"), "Priority": p.get("priority") if p.get("priority") is not None else old.get("Priority"), "Effect": p.get("effect") or old.get("Effect"), "Actions": sorted(p["actions"]) if p.get("actions") is not None else old.get("Actions"), "Resources": sorted(p["resources"]) if p.get("resources") is not None else old.get("Resources"), "Username": p["username"], "ClientId": p["client_id"], "Ip": p["ip"], "Retain": p.get("retain") if p.get("retain") is not None else old.get("Retain"), "Qos": sorted(str(x) for x in p["qos"]) if p.get("qos") is not None else old.get("Qos"), "Remark": p["remark"]}
def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "policy_id": {"type": "int"}, "name": {}, "priority": {"type": "int"}, "effect": {"choices": ["allow", "deny"]}, "actions": {"type": "list", "elements": "str", "choices": ["connect", "pub", "sub"]}, "resources": {"type": "list", "elements": "str"}, "username": {"default": ""}, "client_id": {"default": ""}, "ip": {"default": ""}, "retain": {"type": "int", "choices": [1, 2, 3]}, "qos": {"type": "list", "elements": "int", "choices": [0, 1, 2]}, "remark": {"default": ""}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("policy_id", "name")], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.MqttClient, "mqtt.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, policy=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteAuthorizationPolicy, delete_request(models, p, current["Id"]))
            module.exit_json(changed=True, **(diff or {}), policy=None)
        if not current:
            missing = [k for k in ("name", "priority", "effect", "actions", "resources") if p.get(k) is None]
            if missing: module.fail_json(msg="creation parameters are required for a new MQTT authorization policy", missing=missing)
        before, target = comparable(current) if current else None, desired(p, current)
        if before == target: module.exit_json(changed=False, policy=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            effective = dict(p); effective.update({"name": target["PolicyName"], "priority": target["Priority"], "effect": target["Effect"], "actions": target["Actions"], "resources": target["Resources"], "username": target["Username"], "client_id": target["ClientId"], "ip": target["Ip"], "retain": target["Retain"], "qos": target["Qos"], "remark": target["Remark"]})
            module.sdk_call(client.ModifyAuthorizationPolicy if current else client.CreateAuthorizationPolicy, update_request(models, effective, current["Id"]) if current else create_request(models, effective)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), policy=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__ == "__main__": main()
