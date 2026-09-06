#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: ckafka_user
short_description: Manage Tencent Cloud CKafka users
version_added: "0.14.0"
description: Creates and deletes CKafka users and performs explicit password rotation with the current password.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: CKafka instance ID.}
  name: {type: str, required: true, description: User name.}
  password: {type: str, description: Password for user creation or the new password during rotation.}
  rotate_password: {type: bool, default: false, description: Explicitly replace the password.}
  current_password: {type: str, description: Current password required by CKafka during rotation.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ckafka_user:
    instance_id: ckafka-xxxxxxxx
    name: producer
    password: '{{ vault_ckafka_password }}'
"""
RETURN = r"""user: {description: CKafka user metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.ckafka.v20190819 import ckafka_client, models

    return models, ckafka_client


def describe_request(models, p, offset=0):
    request = models.DescribeUserRequest()
    request.InstanceId, request.SearchWord, request.Offset, request.Limit = p["instance_id"], p["name"], offset, 100
    return request


def create_request(models, p):
    request = models.CreateUserRequest()
    request.InstanceId, request.Name, request.Password = p["instance_id"], p["name"], p["password"]
    return request


def password_request(models, p):
    request = models.ModifyPasswordRequest()
    request.InstanceId, request.Name = p["instance_id"], p["name"]
    request.Password, request.PasswordNew = p["current_password"], p["password"]
    return request


def delete_request(models, p):
    request = models.DeleteUserRequest()
    request.InstanceId, request.Name = p["instance_id"], p["name"]
    return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeUser, describe_request(models, p, offset))
        result = response.Result
        items = list(result.Users or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("Name") == p["name"]:
                return value
        offset += len(items)
        if not items or offset >= int(result.TotalCount or 0):
            return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "name": {"required": True},
            "password": {"no_log": True},
            "rotate_password": {"type": "bool", "default": False},
            "current_password": {"no_log": True},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["rotate_password"] and (not p["password"] or not p["current_password"]):
        module.fail_json(msg="password and current_password are required when rotate_password=true")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CkafkaClient, "ckafka.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, user=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteUser, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), user=current if module.check_mode else None)
        if current and not p["rotate_password"]:
            module.exit_json(changed=False, user=current)
        diff = maybe_diff(module, None if not current else current, {"Name": p["name"]})
        if not module.check_mode:
            if not current:
                if not p["password"]:
                    module.fail_json(msg="password is required when creating a CKafka user")
                module.sdk_call(client.CreateUser, create_request(models, p))
            else:
                module.sdk_call(client.ModifyPassword, password_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), user=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
