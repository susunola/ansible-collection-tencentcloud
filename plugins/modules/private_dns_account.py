#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: private_dns_account
short_description: Manage Tencent Cloud Private DNS cross-account authorization
version_added: "0.14.0"
description:
  - Adds or removes a previously authorized primary account from Private DNS.
  - The target account must complete the Tencent Cloud authorization prerequisite before creation.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired relationship state.}
  uin: {type: str, required: true, description: Target primary account UIN.}
  account: {type: str, required: true, description: Target primary account login name.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.private_dns_account:
    uin: '100000000001'
    account: dns-consumer@example.com
"""
RETURN = r"""account_binding: {description: Effective cross-account relationship., type: dict, returned: always}"""
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.privatedns.v20201028 import models, privatedns_client

    return models, privatedns_client


def account_object(models, uin, account):
    value = models.PrivateDNSAccount()
    value.Uin, value.Account = uin, account
    return value


def mutation_request(models, class_name, uin, account):
    value = getattr(models, class_name)()
    value.Account = account_object(models, uin, account)
    return value


def list_request(models, offset):
    value = models.DescribePrivateDNSAccountListRequest()
    value.Offset, value.Limit = offset, 100
    return value


def find(module, client, models, uin):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribePrivateDNSAccountList, list_request(models, offset))
        items = list(response.AccountSet or [])
        matches.extend(item._serialize(allow_none=True) for item in items if str(item.Uin) == str(uin))
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple Private DNS account relationships have the same UIN", uin=uin)
    return matches[0] if matches else None


def wait(module, client, models, uin, present):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find(module, client, models, uin)
        if bool(current) == present:
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for Private DNS account relationship", uin=uin, expected="present" if present else "absent")
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "uin": {"required": True}, "account": {"required": True}},
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.PrivatednsClient, "privatedns.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["uin"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, account_binding=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeletePrivateDNSAccount, mutation_request(models, "DeletePrivateDNSAccountRequest", p["uin"], p["account"]))
                current = wait(module, client, models, p["uin"], False)
            module.exit_json(changed=True, **(diff or {}), account_binding=current)
        target = {"Uin": p["uin"], "Account": p["account"]}
        if current:
            if current.get("Account") != p["account"]:
                module.fail_json(msg="account name for an existing UIN cannot be updated in place; remove the relationship first", current=current)
            module.exit_json(changed=False, account_binding=current)
        diff = maybe_diff(module, None, target)
        if not module.check_mode:
            module.sdk_call(client.CreatePrivateDNSAccount, mutation_request(models, "CreatePrivateDNSAccountRequest", p["uin"], p["account"]))
            current = wait(module, client, models, p["uin"], True)
        module.exit_json(changed=True, **(diff or {}), account_binding=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
