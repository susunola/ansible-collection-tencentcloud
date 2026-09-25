#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: redis_account
short_description: Manage TencentDB for Redis accounts
version_added: "0.14.0"
description: Creates, updates and deletes a Redis account with explicit password rotation.
options:
  state:
    description:
      - C(present) creates the account with V(CreateInstanceAccount) when it does not exist and updates it with
        V(ModifyInstanceAccount) when it differs. C(absent) deletes it with V(DeleteInstanceAccount).
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - Redis instance ID.
    type: str
    required: true
  name:
    description:
      - Account name.
    type: str
    required: true
  password:
    description:
      - Password used for creation or explicit rotation.
    type: str
  rotate_password:
    description:
      - Explicitly rotate the password.
    type: bool
    default: false
  privilege:
    description:
      - Account privilege.
    type: str
    choices: [r, w, rw]
    default: rw
  readonly_policy:
    description:
      - Read-request routing policy.
    type: list
    default: [master]
    elements: str
  remark:
    description:
      - Account description.
    type: str
    default: ''
  encrypt_password:
    description:
      - Enable encrypted password transmission.
    type: bool
    default: false

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
  - module: susunola.tencentcloud.redis_account_info
    description: Gather information about Tencent Cloud Redis accounts.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.redis_account:
    instance_id: crs-xxxxxxxx
    name: application
    password: '{{ vault_redis_password }}'
    privilege: rw

- name: Delete the account
  susunola.tencentcloud.redis_account:
    state: absent
    instance_id: crs-xxxxxxxx
    name: application
"""
RETURN = r"""account:
  description:
    - Redis account metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    InstanceId: crs-abc123
    AccountName: application
    AccountPassword: new-secret
    Privilege: rw
    ReadonlyPolicy:
      - master
    Remark: billing app
    EncryptPassword: false
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.redis.v20180412 import models, redis_client

    return models, redis_client


def build_describe(models, instance_id):
    request = models.DescribeInstanceAccountRequest()
    request.InstanceId, request.Offset, request.Limit = instance_id, 0, 100
    return request


def build_create(models, p):
    request = models.CreateInstanceAccountRequest()
    request.InstanceId, request.AccountName, request.AccountPassword = p["instance_id"], p["name"], p["password"]
    request.Privilege, request.ReadonlyPolicy, request.Remark = p["privilege"], p["readonly_policy"], p["remark"]
    request.EncryptPassword = p["encrypt_password"]
    return request


def build_update(models, p, include_password=False):
    request = models.ModifyInstanceAccountRequest()
    request.InstanceId, request.AccountName = p["instance_id"], p["name"]
    request.AccountPassword = p["password"] if include_password else None
    request.Privilege, request.ReadonlyPolicy, request.Remark = p["privilege"], p["readonly_policy"], p["remark"]
    request.EncryptPassword = p["encrypt_password"]
    return request


def build_delete(models, p):
    request = models.DeleteInstanceAccountRequest()
    request.InstanceId, request.AccountName = p["instance_id"], p["name"]
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeInstanceAccount, build_describe(models, p["instance_id"]))
    matches = [x._serialize(allow_none=True) for x in list(response.Accounts or []) if x.AccountName == p["name"]]
    return matches[0] if matches else None


def desired(p):
    return {"AccountName": p["name"], "Privilege": p["privilege"], "ReadonlyPolicy": sorted(p["readonly_policy"]), "Remark": p["remark"]}


def comparable(value):
    return {
        "AccountName": value.get("AccountName"),
        "Privilege": value.get("Privilege"),
        "ReadonlyPolicy": sorted(value.get("ReadonlyPolicy") or []),
        "Remark": value.get("Remark") or "",
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "name": {"required": True},
            "password": {"no_log": True},
            "rotate_password": {"type": "bool", "default": False},
            "privilege": {"choices": ["r", "w", "rw"], "default": "rw"},
            "readonly_policy": {"type": "list", "elements": "str", "default": ["master"]},
            "remark": {"default": ""},
            "encrypt_password": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["rotate_password"] and not p["password"]:
        module.fail_json(msg="password is required when rotate_password=true")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.RedisClient, "redis.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, account=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteInstanceAccount, build_delete(models, p))
            module.exit_json(changed=True, **(diff or {}), account=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target and not p["rotate_password"]:
            module.exit_json(changed=False, account=current)
        if not current and not p["password"]:
            module.fail_json(msg="password is required when creating")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyInstanceAccount, build_update(models, p, p["rotate_password"]))
            else:
                module.sdk_call(client.CreateInstanceAccount, build_create(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), account=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
