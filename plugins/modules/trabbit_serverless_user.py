#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: trabbit_serverless_user
short_description: Manage Tencent Cloud RabbitMQ Serverless users
version_added: "0.14.0"
description: Creates, updates and deletes RabbitMQ Serverless users with explicit password rotation.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - RabbitMQ Serverless instance ID.
    type: str
    required: true
  name:
    description:
      - Username.
    type: str
    required: true
  password:
    description:
      - Password for creation or explicit rotation.
    type: str
  rotate_password:
    description:
      - Explicitly replace the password.
    type: bool
    default: false
  description:
    description:
      - User description.
    type: str
    default: ''
  tags:
    description:
      - RabbitMQ Management access tags.
    type: list
    default: []
    elements: str
  max_connections:
    description:
      - Maximum connections.
    type: int
  max_channels:
    description:
      - Maximum channels.
    type: int

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
seealso:
  - module: susunola.tencentcloud.trabbit_serverless_user_info
    description: Gather information about Tencent Cloud TRABBIT serverless users.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.trabbit_serverless_user:
    instance_id: amqp-xxxxxxxx
    name: application
    password: "{{ vault_rabbitmq_password }}"
    tags: [management]
"""
RETURN = r"""user:
  description:
    - RabbitMQ Serverless user metadata without password.
  returned: always
  type: dict"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.trabbit.v20230418 import models, trabbit_client

    return models, trabbit_client


def describe_request(models, p, offset=0):
    r = models.DescribeRabbitMQServerlessUserRequest()
    r.InstanceId, r.User, r.Offset, r.Limit = p["instance_id"], p["name"], offset, 100
    return r


def _apply(r, p, creating=False):
    r.InstanceId, r.User = p["instance_id"], p["name"]
    if creating or p["rotate_password"]:
        r.Password = p.get("password")
    r.Description, r.Tags = p["description"], sorted(set(p["tags"]))
    r.MaxConnections, r.MaxChannels = p.get("max_connections"), p.get("max_channels")
    return r


def create_request(models, p):
    return _apply(models.CreateRabbitMQServerlessUserRequest(), p, True)


def update_request(models, p):
    return _apply(models.ModifyRabbitMQServerlessUserRequest(), p)


def delete_request(models, p):
    r = models.DeleteRabbitMQServerlessUserRequest()
    r.InstanceId, r.User = p["instance_id"], p["name"]
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeRabbitMQServerlessUser, describe_request(models, p))
    matches = []
    for item in response.RabbitMQUserList or []:
        value = item._serialize(allow_none=True)
        value.pop("Password", None)
        if value.get("User") == p["name"]:
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple RabbitMQ Serverless users matched")
    return matches[0] if matches else None


def comparable(value):
    return {
        "User": value.get("User"),
        "Description": value.get("Description") or "",
        "Tags": sorted(value.get("Tags") or []),
        "MaxConnections": value.get("MaxConnections"),
        "MaxChannels": value.get("MaxChannels"),
    }


def desired(p, current=None):
    current = current or {}
    return {
        "User": p["name"],
        "Description": p["description"],
        "Tags": sorted(set(p["tags"])),
        "MaxConnections": p["max_connections"] if p.get("max_connections") is not None else current.get("MaxConnections"),
        "MaxChannels": p["max_channels"] if p.get("max_channels") is not None else current.get("MaxChannels"),
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "name": {"required": True},
            "password": {"no_log": True},
            "rotate_password": {"type": "bool", "default": False},
            "description": {"default": ""},
            "tags": {"type": "list", "elements": "str", "default": []},
            "max_connections": {"type": "int"},
            "max_channels": {"type": "int"},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["rotate_password"] and not p.get("password"):
        module.fail_json(msg="password is required when rotate_password=true")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TrabbitClient, "trabbit.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, user=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteRabbitMQServerlessUser, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), user=current if module.check_mode else None)
        before, target = comparable(current) if current else None, desired(p, current)
        if before == target and not p["rotate_password"]:
            module.exit_json(changed=False, user=current)
        if not current and not p.get("password"):
            module.fail_json(msg="password is required when creating a RabbitMQ Serverless user")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(
                client.ModifyRabbitMQServerlessUser if current else client.CreateRabbitMQServerlessUser,
                update_request(models, p) if current else create_request(models, p),
            )
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), user=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
