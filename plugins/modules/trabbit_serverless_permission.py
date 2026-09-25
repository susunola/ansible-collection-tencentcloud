#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: trabbit_serverless_permission
short_description: Manage Tencent Cloud RabbitMQ Serverless permissions
version_added: "0.14.0"
description: Reconciles a user's configure, write and read regex permissions for a Serverless virtual host.
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
  user:
    description:
      - Username.
    type: str
    required: true
  virtual_host:
    description:
      - Virtual-host name.
    type: str
    required: true
  configure_regex:
    description:
      - Configure-operation resource regex.
    type: str
    default: .*
  write_regex:
    description:
      - Write-operation resource regex.
    type: str
    default: .*
  read_regex:
    description:
      - Read-operation resource regex.
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
seealso:
  - module: susunola.tencentcloud.trabbit_serverless_permission_info
    description: Gather information about Tencent Cloud TRABBIT serverless permissions.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.trabbit_serverless_permission:
    instance_id: amqp-xxxxxxxx
    user: application
    virtual_host: production
    configure_regex: '^orders\.'
    write_regex: '^orders\.'
    read_regex: '^orders\.'

- name: Delete the permission
  susunola.tencentcloud.trabbit_serverless_permission:
    state: absent
    instance_id: amqp-xxxxxxxx
    user: application
    virtual_host: production
"""
RETURN = r"""permission:
  description:
    - RabbitMQ Serverless permission metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    InstanceId: amqp-abc123
    User: application
    VirtualHost: production
    ConfigRegexp: ^orders\.
    WriteRegexp: ^invoices\.
    ReadRegexp: ^orders\.
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.trabbit.v20230418 import models, trabbit_client

    return models, trabbit_client


def describe_request(models, p, offset=0):
    r = models.DescribeRabbitMQServerlessPermissionRequest()
    r.InstanceId, r.User, r.VirtualHost, r.Offset, r.Limit = p["instance_id"], p["user"], p["virtual_host"], offset, 100
    return r


def modify_request(models, p):
    r = models.ModifyRabbitMQServerlessPermissionRequest()
    r.InstanceId, r.User, r.VirtualHost = p["instance_id"], p["user"], p["virtual_host"]
    r.ConfigRegexp, r.WriteRegexp, r.ReadRegexp = p["configure_regex"], p["write_regex"], p["read_regex"]
    return r


def delete_request(models, p):
    r = models.DeleteRabbitMQServerlessPermissionRequest()
    r.InstanceId, r.User, r.VirtualHost = p["instance_id"], p["user"], p["virtual_host"]
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeRabbitMQServerlessPermission, describe_request(models, p))
    for item in response.RabbitMQPermissionList or []:
        value = item._serialize(allow_none=True)
        if value.get("User") == p["user"] and value.get("VirtualHost") == p["virtual_host"]:
            return value
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
    client = module.create_client(cm.TrabbitClient, "trabbit.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, permission=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteRabbitMQServerlessPermission, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), permission=current if module.check_mode else None)
        before, target = comparable(current) if current else None, desired(p)
        if before == target:
            module.exit_json(changed=False, permission=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyRabbitMQServerlessPermission, modify_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), permission=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
