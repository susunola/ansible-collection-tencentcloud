#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dcdb_account
short_description: Manage Tencent Cloud DCDB accounts
version_added: "0.14.0"
description: Creates and deletes accounts, updates descriptions and explicitly rotates passwords.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: DCDB instance ID.}
  username: {type: str, required: true, description: Account name.}
  host: {type: str, default: '%', description: Account host expression.}
  password: {type: str, description: Password for creation or explicit rotation.}
  rotate_password: {type: bool, default: false, description: Explicitly replace the account password.}
  description: {type: str, default: '', description: Account description.}
  read_only: {type: int, choices: [0, 1, 2, 3], default: 0, description: Creation-time read-routing policy.}
  delay_threshold: {type: int, default: 10, description: Creation-time replica-delay threshold.}
  sticky_replica: {type: bool, default: false, description: Creation-time fixed-replica policy.}
  max_user_connections: {type: int, default: 0, description: Creation-time maximum connections; zero means unlimited.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dcdb_account:
    instance_id: tdsqlshard-xxxxxxxx
    username: application
    password: '{{ vault_dcdb_password }}'
"""
RETURN = r"""account: {description: DCDB account metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.dcdb.v20180411 import models, dcdb_client

    return models, dcdb_client


def identity(request, params):
    request.InstanceId, request.UserName, request.Host = params["instance_id"], params["username"], params["host"]
    return request


def desired(params):
    return {
        "UserName": params["username"],
        "Host": params["host"],
        "Description": params["description"],
        "ReadOnly": params["read_only"],
        "DelayThresh": params["delay_threshold"],
        "SlaveConst": int(params["sticky_replica"]),
        "MaxUserConnections": params["max_user_connections"],
    }


def comparable(value):
    return {key: value.get(key) for key in ("UserName", "Host", "Description", "ReadOnly", "DelayThresh", "SlaveConst", "MaxUserConnections")}


def find(module, client, models, params):
    request = models.DescribeAccountsRequest()
    request.InstanceId = params["instance_id"]
    response = module.sdk_call(client.DescribeAccounts, request)
    for item in response.Users or []:
        value = item._serialize(allow_none=True)
        if value.get("UserName") == params["username"] and (value.get("Host") or "%") == params["host"]:
            return value
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "username": {"required": True},
            "host": {"default": "%"},
            "password": {"no_log": True},
            "rotate_password": {"type": "bool", "default": False},
            "description": {"default": ""},
            "read_only": {"type": "int", "choices": [0, 1, 2, 3], "default": 0},
            "delay_threshold": {"type": "int", "default": 10},
            "sticky_replica": {"type": "bool", "default": False},
            "max_user_connections": {"type": "int", "default": 0},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["rotate_password"] and not p["password"]:
        module.fail_json(msg="password is required when rotate_password=true")
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.DcdbClient, "dcdb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, account=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteAccount, identity(models.DeleteAccountRequest(), p))
            module.exit_json(changed=True, **(diff or {}), account=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target and not p["rotate_password"]:
            module.exit_json(changed=False, account=current)
        if current:
            require_immutable_unchanged(module, before, target, ("ReadOnly", "DelayThresh", "SlaveConst", "MaxUserConnections"), "DCDB account")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current is None:
                if not p["password"]:
                    module.fail_json(msg="password is required when creating a DCDB account")
                request = identity(models.CreateAccountRequest(), p)
                request.Password, request.Description = p["password"], p["description"]
                request.ReadOnly, request.DelayThresh, request.SlaveConst, request.MaxUserConnections = (
                    p["read_only"],
                    p["delay_threshold"],
                    int(p["sticky_replica"]),
                    p["max_user_connections"],
                )
                module.sdk_call(client.CreateAccount, request)
            else:
                if before["Description"] != target["Description"]:
                    request = identity(models.ModifyAccountDescriptionRequest(), p)
                    request.Description = p["description"]
                    module.sdk_call(client.ModifyAccountDescription, request)
                if p["rotate_password"]:
                    request = identity(models.ResetAccountPasswordRequest(), p)
                    request.Password = p["password"]
                    module.sdk_call(client.ResetAccountPassword, request)
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), account=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
