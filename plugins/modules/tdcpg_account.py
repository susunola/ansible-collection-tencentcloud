#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tdcpg_account
short_description: Govern a TDSQL-C PostgreSQL account
version_added: "0.14.0"
description: Reconciles an existing account description and performs explicitly requested password rotation.
options:
  cluster_id: {type: str, required: true, description: Cluster ID.}
  account_name: {type: str, required: true, description: Existing database account name.}
  description: {type: str, description: Account description.}
  password: {type: str, no_log: true, description: New password used only with rotate_password=true.}
  rotate_password: {type: bool, default: false, description: Explicitly rotate the write-only password.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdcpg_account:
    cluster_id: tdcpg-xxxxxxxx
    account_name: root
    description: Platform administrator
"""
RETURN = r"""account: {description: Effective account metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tdcpg.v20211118 import models, tdcpg_client

    return models, tdcpg_client


def describe_request(models, cluster_id):
    r = models.DescribeAccountsRequest()
    r.ClusterId = cluster_id
    return r


def description_request(models, p):
    r = models.ModifyAccountDescriptionRequest()
    r.ClusterId, r.AccountName, r.AccountDescription = p["cluster_id"], p["account_name"], p["description"]
    return r


def password_request(models, p):
    r = models.ResetAccountPasswordRequest()
    r.ClusterId, r.AccountName, r.AccountPassword = p["cluster_id"], p["account_name"], p["password"]
    return r


def find(module, client, models, p):
    values = module.sdk_call(client.DescribeAccounts, describe_request(models, p["cluster_id"])).AccountSet or []
    matches = [x._serialize(allow_none=True) for x in values if x.AccountName == p["account_name"]]
    if not matches:
        module.fail_json(msg="TDSQL-C PostgreSQL account was not found", cluster_id=p["cluster_id"], account_name=p["account_name"])
    return matches[0]


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "cluster_id": {"required": True},
            "account_name": {"required": True},
            "description": {},
            "password": {"no_log": True},
            "rotate_password": {"type": "bool", "default": False},
        },
        required_if=[("rotate_password", True, ("password",))],
        supports_check_mode=True,
    )
    p = module.params
    if p.get("description") is not None and len(p["description"]) > 256:
        module.fail_json(msg="description must not exceed 256 characters")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdcpgClient, "tdcpg.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        description_drift = p.get("description") is not None and current.get("AccountDescription") != p["description"]
        if not description_drift and not p["rotate_password"]:
            module.exit_json(changed=False, account=current)
        target = dict(current)
        if p.get("description") is not None:
            target["AccountDescription"] = p["description"]
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if description_drift:
                module.sdk_call(client.ModifyAccountDescription, description_request(models, p))
            if p["rotate_password"]:
                module.sdk_call(client.ResetAccountPassword, password_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), account=current if not module.check_mode else target, password_rotated=p["rotate_password"])
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
