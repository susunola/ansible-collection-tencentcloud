#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: redis_account
short_description: Manage TencentDB for Redis accounts
version_added: "0.14.0"
description: Creates, updates and deletes a Redis account with explicit password rotation.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: Redis instance ID.}
  name: {type: str, required: true, description: Account name.}
  password: {type: str, description: Password used for creation or explicit rotation.}
  rotate_password: {type: bool, default: false, description: Explicitly rotate the password.}
  privilege: {type: str, choices: [r, w, rw], default: rw, description: Account privilege.}
  readonly_policy: {type: list, elements: str, default: [master], description: Read-request routing policy.}
  remark: {type: str, default: '', description: Account description.}
  encrypt_password: {type: bool, default: false, description: Enable encrypted password transmission.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.redis_account:
    instance_id: crs-xxxxxxxx
    name: application
    password: '{{ vault_redis_password }}'
    privilege: rw
'''
RETURN = r'''account: {description: Redis account metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


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
    return {"AccountName": value.get("AccountName"), "Privilege": value.get("Privilege"), "ReadonlyPolicy": sorted(value.get("ReadonlyPolicy") or []), "Remark": value.get("Remark") or ""}


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "name": {"required": True},
        "password": {"no_log": True}, "rotate_password": {"type": "bool", "default": False}, "privilege": {"choices": ["r", "w", "rw"], "default": "rw"},
        "readonly_policy": {"type": "list", "elements": "str", "default": ["master"]}, "remark": {"default": ""}, "encrypt_password": {"type": "bool", "default": False},
    }, supports_check_mode=True)
    p = module.params
    if p["rotate_password"] and not p["password"]:
        module.fail_json(msg="password is required when rotate_password=true")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.RedisClient, "redis.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, account=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteInstanceAccount, build_delete(models, p))
            module.exit_json(changed=True, **(diff or {}), account=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target and not p["rotate_password"]: module.exit_json(changed=False, account=current)
        if not current and not p["password"]: module.fail_json(msg="password is required when creating")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current: module.sdk_call(client.ModifyInstanceAccount, build_update(models, p, p["rotate_password"]))
            else: module.sdk_call(client.CreateInstanceAccount, build_create(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), account=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
