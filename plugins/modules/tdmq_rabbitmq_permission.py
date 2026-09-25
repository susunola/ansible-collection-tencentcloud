#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tdmq_rabbitmq_permission
short_description: Manage TDMQ RabbitMQ virtual host permissions
version_added: "0.14.0"
description: Creates or updates a user's configure, write and read regex permissions for a virtual host and removes the binding when absent.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - TDMQ RabbitMQ instance ID.
    type: str
    required: true
  user:
    description:
      - RabbitMQ username.
    type: str
    required: true
  virtual_host:
    description:
      - Virtual host name.
    type: str
    required: true
  configure_regex:
    description:
      - Resource-name regex allowed for configure operations.
    type: str
    default: .*
  write_regex:
    description:
      - Resource-name regex allowed for write operations.
    type: str
    default: .*
  read_regex:
    description:
      - Resource-name regex allowed for read operations.
    type: str
    default: .*

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
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmq_rabbitmq_permission:
    instance_id: amqp-xxxxxxxx
    user: application
    virtual_host: production
    configure_regex: '^orders\\.'
    write_regex: '^orders\\.'
    read_regex: '^orders\\.'

- name: Delete the permission
  susunola.tencentcloud.tdmq_rabbitmq_permission:
    state: absent
    instance_id: amqp-xxxxxxxx
    user: application
    virtual_host: production
"""
RETURN = r"""permission:
  description:
    - RabbitMQ virtual host permission metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    User: application
    VirtualHost: production
    ConfigRegexp: ^orders\.
    WriteRegexp: ^orders\.
    ReadRegexp: ^orders\.
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client

    return models, tdmq_client


def describe_request(models, p, offset=0):
    request = models.DescribeRabbitMQPermissionRequest()
    request.InstanceId, request.User, request.VirtualHost = p["instance_id"], p["user"], p["virtual_host"]
    request.Offset, request.Limit = offset, 100
    return request


def modify_request(models, p):
    request = models.ModifyRabbitMQPermissionRequest()
    request.InstanceId, request.User, request.VirtualHost = p["instance_id"], p["user"], p["virtual_host"]
    request.ConfigRegexp, request.WriteRegexp, request.ReadRegexp = p["configure_regex"], p["write_regex"], p["read_regex"]
    return request


def delete_request(models, p):
    request = models.DeleteRabbitMQPermissionRequest()
    request.InstanceId, request.User, request.VirtualHost = p["instance_id"], p["user"], p["virtual_host"]
    return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeRabbitMQPermission, describe_request(models, p, offset))
        items = list(response.RabbitMQPermissionList or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("User") == p["user"] and value.get("VirtualHost") == p["virtual_host"]:
                return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            return None


def comparable(value):
    return {
        "User": value.get("User"),
        "VirtualHost": value.get("VirtualHost"),
        "ConfigRegexp": value.get("ConfigRegexp"),
        "WriteRegexp": value.get("WriteRegexp"),
        "ReadRegexp": value.get("ReadRegexp"),
    }


def desired(p):
    return {
        "User": p["user"],
        "VirtualHost": p["virtual_host"],
        "ConfigRegexp": p["configure_regex"],
        "WriteRegexp": p["write_regex"],
        "ReadRegexp": p["read_regex"],
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "user": {"required": True},
            "virtual_host": {"required": True},
            "configure_regex": {"default": ".*"},
            "write_regex": {"default": ".*"},
            "read_regex": {"default": ".*"},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, permission=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteRabbitMQPermission, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), permission=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, permission=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyRabbitMQPermission, modify_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), permission=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
