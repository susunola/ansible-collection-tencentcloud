#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: tdmq_rabbitmq_user
short_description: Manage TDMQ RabbitMQ users
version_added: "0.14.0"
description: Creates, updates and deletes RabbitMQ users and performs explicit password rotation.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: TDMQ RabbitMQ instance ID.}
  name: {type: str, required: true, description: RabbitMQ username.}
  password: {type: str, description: Password for creation or explicit rotation.}
  rotate_password: {type: bool, default: false, description: Explicitly replace the password.}
  description: {type: str, default: '', description: User description.}
  tags: {type: list, elements: str, default: [], description: RabbitMQ Management access tags.}
  max_connections: {type: int, description: Maximum connections. Omit to preserve the service default or current value.}
  max_channels: {type: int, description: Maximum channels. Omit to preserve the service default or current value.}
  cam_auth_enabled: {type: bool, default: false, description: Enable CAM authentication.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdmq_rabbitmq_user:
    instance_id: amqp-xxxxxxxx
    name: application
    password: '{{ vault_rabbitmq_password }}'
    tags: [management]
    max_connections: 100
'''
RETURN = r'''user: {description: RabbitMQ user metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client
    return models, tdmq_client


def describe_request(models, p, offset=0):
    request = models.DescribeRabbitMQUserRequest(); request.InstanceId, request.User, request.Offset, request.Limit = p["instance_id"], p["name"], offset, 100; return request


def apply_request(request, p, creating=False):
    request.InstanceId, request.User = p["instance_id"], p["name"]
    if creating or p.get("rotate_password"): request.Password = p.get("password")
    request.Description, request.Tags = p["description"], sorted(set(p["tags"]))
    if p.get("max_connections") is not None: request.MaxConnections = p["max_connections"]
    if p.get("max_channels") is not None: request.MaxChannels = p["max_channels"]
    request.EnableCamAuth = p["cam_auth_enabled"]
    return request


def create_request(models, p): return apply_request(models.CreateRabbitMQUserRequest(), p, True)
def update_request(models, p): return apply_request(models.ModifyRabbitMQUserRequest(), p)


def delete_request(models, p):
    request = models.DeleteRabbitMQUserRequest(); request.InstanceId, request.User = p["instance_id"], p["name"]; return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeRabbitMQUser, describe_request(models, p, offset)); items = list(response.RabbitMQUserList or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("User") == p["name"]: return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0): return None


def comparable(value):
    return {"User": value.get("User"), "Description": value.get("Description") or "", "Tags": sorted(value.get("Tags") or []), "MaxConnections": value.get("MaxConnections"), "MaxChannels": value.get("MaxChannels"), "CamAuthEnabled": bool(value.get("CamAuthEnabled"))}


def desired(p, current=None):
    current = current or {}
    return {"User": p["name"], "Description": p["description"], "Tags": sorted(set(p["tags"])), "MaxConnections": p["max_connections"] if p["max_connections"] is not None else current.get("MaxConnections"), "MaxChannels": p["max_channels"] if p["max_channels"] is not None else current.get("MaxChannels"), "CamAuthEnabled": p["cam_auth_enabled"]}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "name": {"required": True}, "password": {"no_log": True}, "rotate_password": {"type": "bool", "default": False}, "description": {"default": ""}, "tags": {"type": "list", "elements": "str", "default": []}, "max_connections": {"type": "int"}, "max_channels": {"type": "int"}, "cam_auth_enabled": {"type": "bool", "default": False}}, supports_check_mode=True)
    p = module.params
    if p["rotate_password"] and not p["password"]: module.fail_json(msg="password is required when rotate_password=true")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, user=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteRabbitMQUser, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), user=current if module.check_mode else None)
        target, before = desired(p, current), comparable(current) if current else None
        if before == target and not p["rotate_password"]: module.exit_json(changed=False, user=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if not current and not p["password"]: module.fail_json(msg="password is required when creating a RabbitMQ user")
            module.sdk_call(client.ModifyRabbitMQUser if current else client.CreateRabbitMQUser, update_request(models, p) if current else create_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), user=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
