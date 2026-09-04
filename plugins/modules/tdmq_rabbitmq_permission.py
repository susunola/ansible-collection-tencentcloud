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
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: TDMQ RabbitMQ instance ID.}
  user: {type: str, required: true, description: RabbitMQ username.}
  virtual_host: {type: str, required: true, description: Virtual host name.}
  configure_regex: {type: str, default: '.*', description: Resource-name regex allowed for configure operations.}
  write_regex: {type: str, default: '.*', description: Resource-name regex allowed for write operations.}
  read_regex: {type: str, default: '.*', description: Resource-name regex allowed for read operations.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
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
"""
RETURN = r"""permission: {description: RabbitMQ virtual host permission metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


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
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
