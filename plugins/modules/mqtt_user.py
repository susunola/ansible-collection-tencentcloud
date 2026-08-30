#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: mqtt_user
short_description: Manage Tencent Cloud MQTT users
version_added: "0.14.0"
description: Creates, updates and deletes MQTT username/password identities. Passwords are write-only and used only during creation.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: MQTT instance ID.}
  username: {type: str, required: true, description: MQTT username.}
  password: {type: str, description: Password required for creation; the API cannot update or read it.}
  remark: {type: str, default: '', description: User remark.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.mqtt_user:
    instance_id: mqtt-xxxxxxxx
    username: application
    password: "{{ vault_mqtt_password }}"
'''
RETURN = r'''user: {description: Effective MQTT user metadata without password., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.mqtt.v20240516 import models, mqtt_client
    return models, mqtt_client
def describe_request(models, p):
    r = models.DescribeUserListRequest(); r.InstanceId, r.Offset, r.Limit = p["instance_id"], 0, 100; return r
def create_request(models, p):
    r = models.CreateUserRequest(); r.InstanceId, r.Username, r.Password, r.Remark = p["instance_id"], p["username"], p["password"], p["remark"]; return r
def update_request(models, p):
    r = models.ModifyUserRequest(); r.InstanceId, r.Username, r.Remark = p["instance_id"], p["username"], p["remark"]; return r
def delete_request(models, p):
    r = models.DeleteUserRequest(); r.InstanceId, r.Username = p["instance_id"], p["username"]; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeUserList, describe_request(models, p)); matches = []
    for item in response.Data or []:
        value = item._serialize(allow_none=True); value.pop("Password", None)
        if value.get("Username") == p["username"]: matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple MQTT users matched the username")
    return matches[0] if matches else None
def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "username": {"required": True}, "password": {"no_log": True}, "remark": {"default": ""}}, supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.MqttClient, "mqtt.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, user=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteUser, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), user=None)
        if not current and not p.get("password"): module.fail_json(msg="password is required when creating an MQTT user")
        target = {"Username": p["username"], "Remark": p["remark"]}; before = None if not current else {"Username": current.get("Username"), "Remark": current.get("Remark") or ""}
        if before == target: module.exit_json(changed=False, user=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode: module.sdk_call(client.ModifyUser if current else client.CreateUser, update_request(models, p) if current else create_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), user=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__ == "__main__": main()
