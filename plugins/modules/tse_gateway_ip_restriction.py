#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_ip_restriction
short_description: Manage IP access control on a Tencent Cloud TSE gateway resource
version_added: "0.14.0"
description: Creates, updates and deletes the IP restriction plugin bound to one gateway service or route.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  scope: {type: str, choices: [service, route], required: true, description: Bound resource type.}
  resource_id: {type: str, required: true, description: Service or route ID.}
  enabled: {type: bool, description: Whether the plugin is enabled; creation defaults to true.}
  restriction_type: {type: str, choices: [whiteList, blackList], description: Allow-list or deny-list behavior.}
  addresses: {type: list, elements: str, description: Exact IP addresses or CIDR ranges.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_ip_restriction:
    gateway_id: gateway-xxxxxxxx
    scope: service
    resource_id: service-xxxxxxxx
    restriction_type: whiteList
    addresses: [10.0.0.0/8, 192.0.2.10]
"""
RETURN = r"""ip_restriction: {description: Effective IP restriction policy., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def request(cls, p, target=None):
    r = cls()
    r.GatewayId, r.SourceType, r.SourceId = p["gateway_id"], p["scope"], p["resource_id"]
    for key, value in (target or {}).items():
        setattr(r, key, value)
    return r


def get_current(module, client, models, p):
    response = module.sdk_call(client.DescribeCloudNativeAPIGatewayIPRestriction, request(models.DescribeCloudNativeAPIGatewayIPRestrictionRequest, p))
    result = response.Result
    return result._serialize(allow_none=True) if result else None


def target_config(module, p, current):
    restriction = p.get("restriction_type") or (current or {}).get("RestrictionType")
    addresses = p.get("addresses") if p.get("addresses") is not None else (current or {}).get("AddressList")
    if not restriction or addresses is None:
        module.fail_json(msg="restriction_type and addresses are required when creating an IP restriction")
    return {
        "Enabled": p.get("enabled") if p.get("enabled") is not None else (current or {}).get("Enabled", True),
        "RestrictionType": restriction,
        "AddressList": addresses,
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "gateway_id": {"required": True},
            "scope": {"choices": ["service", "route"], "required": True},
            "resource_id": {"required": True},
            "enabled": {"type": "bool"},
            "restriction_type": {"choices": ["whiteList", "blackList"]},
            "addresses": {"type": "list", "elements": "str"},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = get_current(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, ip_restriction=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCloudNativeAPIGatewayIPRestriction, request(models.DeleteCloudNativeAPIGatewayIPRestrictionRequest, p))
            module.exit_json(changed=True, **(diff or {}), ip_restriction=None)
        target = target_config(module, p, current)
        before = {key: (current or {}).get(key) for key in target}
        if current and before == target:
            module.exit_json(changed=False, ip_restriction=current)
        diff = maybe_diff(module, before if current else None, target)
        if not module.check_mode:
            module.sdk_call(
                client.CreateOrModifyCloudNativeAPIGatewayIPRestriction, request(models.CreateOrModifyCloudNativeAPIGatewayIPRestrictionRequest, p, target)
            )
            current = get_current(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), ip_restriction=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
