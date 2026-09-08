#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dcdb_security_config
short_description: Manage Tencent Cloud DCDB encryption, SSL and security groups
version_added: "0.14.0"
description:
  - Reconciles explicitly supplied DCDB security controls.
  - Data-at-rest encryption is one-way and cannot be disabled after activation.
options:
  instance_id: {type: str, required: true, description: DCDB instance ID.}
  encryption_enabled: {type: bool, description: Enable irreversible data-at-rest encryption.}
  ssl_enabled: {type: bool, description: Enable or disable instance SSL authentication.}
  security_group_ids: {type: list, elements: str, description: Complete desired security-group ID set.}
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dcdb_security_config:
    instance_id: tdsqlshard-xxxxxxxx
    encryption_enabled: true
    ssl_enabled: true
    security_group_ids: [sg-aaaaaaaa, sg-bbbbbbbb]
"""
RETURN = r"""security_config: {description: Effective normalized DCDB security controls., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dcdb.v20180411 import models, dcdb_client

    return models, dcdb_client


def instance_request(cls, instance_id):
    request = cls()
    request.InstanceId = instance_id
    return request


def describe(module, client, models, params):
    result = {}
    if params.get("encryption_enabled") is not None:
        response = module.sdk_call(client.DescribeDBEncryptAttributes, instance_request(models.DescribeDBEncryptAttributesRequest, params["instance_id"]))
        result["encryption_enabled"] = response.EncryptStatus == 1
    if params.get("ssl_enabled") is not None:
        response = module.sdk_call(client.DescribeInstanceSSLAttributes, instance_request(models.DescribeInstanceSSLAttributesRequest, params["instance_id"]))
        result["ssl_enabled"] = response.Status in (1, 2)
        result["ssl_status"] = response.Status
    if params.get("security_group_ids") is not None:
        request = instance_request(models.DescribeDBSecurityGroupsRequest, params["instance_id"])
        request.Product = "dcdb"
        response = module.sdk_call(client.DescribeDBSecurityGroups, request)
        result["security_group_ids"] = sorted(group.SecurityGroupId for group in (response.Groups or []))
    return result


def desired(params):
    result = {}
    if params.get("encryption_enabled") is not None:
        result["encryption_enabled"] = params["encryption_enabled"]
    if params.get("ssl_enabled") is not None:
        result["ssl_enabled"] = params["ssl_enabled"]
    if params.get("security_group_ids") is not None:
        result["security_group_ids"] = sorted(set(params["security_group_ids"]))
    return result


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "instance_id": {"required": True},
            "encryption_enabled": {"type": "bool"},
            "ssl_enabled": {"type": "bool"},
            "security_group_ids": {"type": "list", "elements": "str"},
        },
        supports_check_mode=True,
    )
    p = module.params
    if all(p.get(key) is None for key in ("encryption_enabled", "ssl_enabled", "security_group_ids")):
        module.fail_json(msg="at least one DCDB security control must be supplied")
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.DcdbClient, "dcdb.tencentcloudapi.com")
    try:
        current, target = describe(module, client, models, p), desired(p)
        comparable = {key: current.get(key) for key in target}
        if current.get("encryption_enabled") and target.get("encryption_enabled") is False:
            module.fail_json(msg="DCDB data-at-rest encryption cannot be disabled", security_config=current)
        if comparable == target:
            module.exit_json(changed=False, security_config=current)
        diff = maybe_diff(module, comparable, target)
        if not module.check_mode:
            if target.get("encryption_enabled") and not current.get("encryption_enabled"):
                request = instance_request(models.ModifyDBEncryptAttributesRequest, p["instance_id"])
                request.EncryptEnabled = 1
                module.sdk_call(client.ModifyDBEncryptAttributes, request)
                wait_for_state(
                    module,
                    lambda: describe(module, client, models, dict(p, ssl_enabled=None, security_group_ids=None)).get("encryption_enabled"),
                    {True},
                    timeout=p["waiter_timeout"],
                    delay=p["waiter_delay"],
                )
            if "ssl_enabled" in target and current.get("ssl_enabled") != target["ssl_enabled"]:
                request = instance_request(models.ModifyInstanceSSLAttributesRequest, p["instance_id"])
                request.SSLEnabled = int(target["ssl_enabled"])
                module.sdk_call(client.ModifyInstanceSSLAttributes, request)
                wanted_status = 2 if target["ssl_enabled"] else 3
                wait_for_state(
                    module,
                    lambda: describe(module, client, models, dict(p, encryption_enabled=None, security_group_ids=None)).get("ssl_status"),
                    {wanted_status},
                    timeout=p["waiter_timeout"],
                    delay=p["waiter_delay"],
                )
            if "security_group_ids" in target and current.get("security_group_ids") != target["security_group_ids"]:
                request = instance_request(models.ModifyDBInstanceSecurityGroupsRequest, p["instance_id"])
                request.Product = "dcdb"
                request.SecurityGroupIds = target["security_group_ids"]
                module.sdk_call(client.ModifyDBInstanceSecurityGroups, request)
            current = describe(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), security_config=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
