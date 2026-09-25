#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: mariadb_account
short_description: Manage TencentDB for MariaDB accounts
version_added: "0.14.0"
description: Creates and deletes accounts, updates descriptions and explicitly rotates passwords.
options:
  state:
    description:
      - C(present) creates the account with V(CreateAccount) when it does not exist and updates it with V(ModifyAccountDescription)
        or V(ResetAccountPassword) when it differs. C(absent) deletes it with V(DeleteAccount).
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - MariaDB instance ID.
    type: str
    required: true
  username:
    description:
      - Account name.
    type: str
    required: true
  host:
    description:
      - Account host expression.
    type: str
    default: '%'
  password:
    description:
      - Password for creation or explicit rotation.
    type: str
  rotate_password:
    description:
      - Explicitly replace the account password.
    type: bool
    default: false
  description:
    description:
      - Account description.
    type: str
    default: ''
  read_only:
    description:
      - Immutable read-routing policy.
    type: int
    choices: [0, 1, 2, 3]
    default: 0
  delay_threshold:
    description:
      - Immutable replica-delay threshold in seconds.
    type: int
    default: 10
  sticky_replica:
    description:
      - Keep read-only connections on a fixed replica.
    type: bool
    default: false
  max_user_connections:
    description:
      - Immutable maximum connections; zero means unlimited.
    type: int
    default: 0

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
  - module: susunola.tencentcloud.mariadb_account_info
    description: Gather information about Tencent Cloud MariaDB accounts.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.mariadb_account:
    instance_id: tdsql-xxxxxxxx
    username: app
    password: '{{ vault_mariadb_password }}'
    description: Application account

- name: Delete the account
  susunola.tencentcloud.mariadb_account:
    state: absent
    instance_id: tdsql-xxxxxxxx
    username: app
"""
RETURN = r"""account:
  description:
    - MariaDB account metadata.
  returned: always
  type: dict"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, fail_from_sdk_error


def _load():
    from tencentcloud.mariadb.v20170312 import mariadb_client, models

    return models, mariadb_client


def describe_request(models, instance_id):
    request = models.DescribeAccountsRequest()
    request.InstanceId = instance_id
    return request


def create_request(models, p):
    request = models.CreateAccountRequest()
    request.InstanceId, request.UserName, request.Host = p["instance_id"], p["username"], p["host"]
    request.Password, request.Description, request.ReadOnly = p["password"], p["description"], p["read_only"]
    request.DelayThresh, request.SlaveConst, request.MaxUserConnections = p["delay_threshold"], int(p["sticky_replica"]), p["max_user_connections"]
    return request


def description_request(models, p):
    request = models.ModifyAccountDescriptionRequest()
    request.InstanceId, request.UserName, request.Host, request.Description = p["instance_id"], p["username"], p["host"], p["description"]
    return request


def password_request(models, p):
    request = models.ResetAccountPasswordRequest()
    request.InstanceId, request.UserName, request.Host, request.Password = p["instance_id"], p["username"], p["host"], p["password"]
    return request


def delete_request(models, p):
    request = models.DeleteAccountRequest()
    request.InstanceId, request.UserName, request.Host = p["instance_id"], p["username"], p["host"]
    return request


def desired(p):
    return {
        "UserName": p["username"],
        "Host": p["host"],
        "Description": p["description"],
        "ReadOnly": p["read_only"],
        "DelayThresh": p["delay_threshold"],
        "SlaveConst": int(p["sticky_replica"]),
        "MaxUserConnections": p["max_user_connections"],
    }


def comparable(value):
    return {key: value.get(key) for key in ("UserName", "Host", "Description", "ReadOnly", "DelayThresh", "SlaveConst", "MaxUserConnections")}


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeAccounts, describe_request(models, p["instance_id"]))
    for item in list(response.Users or []):
        value = item._serialize(allow_none=True)
        if value.get("UserName") == p["username"] and (value.get("Host") or "%") == p["host"]:
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
    models, cm = _load()
    client = module.create_client(cm.MariadbClient, "mariadb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, account=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteAccount, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), account=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target and not p["rotate_password"]:
            module.exit_json(changed=False, account=current)
        diff = maybe_diff(module, before, target)
        if current:
            require_immutable_unchanged(module, before, target, ("ReadOnly", "DelayThresh", "SlaveConst", "MaxUserConnections"), "MariaDB account")
        if not module.check_mode:
            if not current:
                if not p["password"]:
                    module.fail_json(msg="password is required when creating a MariaDB account")
                module.sdk_call(client.CreateAccount, create_request(models, p))
            else:
                if before["Description"] != target["Description"]:
                    module.sdk_call(client.ModifyAccountDescription, description_request(models, p))
                if p["rotate_password"]:
                    module.sdk_call(client.ResetAccountPassword, password_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), account=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
