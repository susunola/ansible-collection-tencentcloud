#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: trabbit_serverless_user
short_description: Manage Tencent Cloud RabbitMQ Serverless users
version_added: "0.14.0"
description: Creates, updates and deletes RabbitMQ Serverless users with explicit password rotation.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: RabbitMQ Serverless instance ID.}
  name: {type: str, required: true, description: Username.}
  password: {type: str, description: Password for creation or explicit rotation.}
  rotate_password: {type: bool, default: false, description: Explicitly replace the password.}
  description: {type: str, default: '', description: User description.}
  tags: {type: list, elements: str, default: [], description: RabbitMQ Management access tags.}
  max_connections: {type: int, description: Maximum connections.}
  max_channels: {type: int, description: Maximum channels.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.trabbit_serverless_user:
    instance_id: amqp-xxxxxxxx
    name: application
    password: "{{ vault_rabbitmq_password }}"
    tags: [management]
'''
RETURN = r'''user: {description: RabbitMQ Serverless user metadata without password., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.trabbit.v20230418 import models, trabbit_client
    return models, trabbit_client
def describe_request(models, p, offset=0):
    r = models.DescribeRabbitMQServerlessUserRequest(); r.InstanceId, r.User, r.Offset, r.Limit = p["instance_id"], p["name"], offset, 100; return r
def _apply(r, p, creating=False):
    r.InstanceId, r.User = p["instance_id"], p["name"]
    if creating or p["rotate_password"]: r.Password = p.get("password")
    r.Description, r.Tags = p["description"], sorted(set(p["tags"])); r.MaxConnections, r.MaxChannels = p.get("max_connections"), p.get("max_channels"); return r
def create_request(models, p): return _apply(models.CreateRabbitMQServerlessUserRequest(), p, True)
def update_request(models, p): return _apply(models.ModifyRabbitMQServerlessUserRequest(), p)
def delete_request(models, p):
    r = models.DeleteRabbitMQServerlessUserRequest(); r.InstanceId, r.User = p["instance_id"], p["name"]; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeRabbitMQServerlessUser, describe_request(models, p)); matches = []
    for item in response.RabbitMQUserList or []:
        value = item._serialize(allow_none=True); value.pop("Password", None)
        if value.get("User") == p["name"]: matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple RabbitMQ Serverless users matched")
    return matches[0] if matches else None
def comparable(value): return {"User": value.get("User"), "Description": value.get("Description") or "", "Tags": sorted(value.get("Tags") or []), "MaxConnections": value.get("MaxConnections"), "MaxChannels": value.get("MaxChannels")}
def desired(p, current=None):
    current = current or {}; return {"User": p["name"], "Description": p["description"], "Tags": sorted(set(p["tags"])), "MaxConnections": p["max_connections"] if p.get("max_connections") is not None else current.get("MaxConnections"), "MaxChannels": p["max_channels"] if p.get("max_channels") is not None else current.get("MaxChannels")}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "name": {"required": True}, "password": {"no_log": True}, "rotate_password": {"type": "bool", "default": False}, "description": {"default": ""}, "tags": {"type": "list", "elements": "str", "default": []}, "max_connections": {"type": "int"}, "max_channels": {"type": "int"}}, supports_check_mode=True)
    p = module.params
    if p["rotate_password"] and not p.get("password"): module.fail_json(msg="password is required when rotate_password=true")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TrabbitClient, "trabbit.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, user=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteRabbitMQServerlessUser, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), user=current if module.check_mode else None)
        before, target = comparable(current) if current else None, desired(p, current)
        if before == target and not p["rotate_password"]: module.exit_json(changed=False, user=current)
        if not current and not p.get("password"): module.fail_json(msg="password is required when creating a RabbitMQ Serverless user")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyRabbitMQServerlessUser if current else client.CreateRabbitMQServerlessUser, update_request(models, p) if current else create_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), user=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
