#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_waf_protection
short_description: Manage Tencent Cloud TSE gateway WAF protection
version_added: "0.14.0"
description: Reconciles global, service or route WAF protection using per-resource status readback.
options:
  gateway_id: {type: str, required: true, description: Gateway ID.}
  scope: {type: str, choices: [Global, Service, Route], required: true, description: Protection scope.}
  resource_ids: {type: list, elements: str, description: Service or route IDs; required outside Global scope.}
  enabled: {type: bool, required: true, description: Desired WAF protection status.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_waf_protection:
    gateway_id: gateway-xxxxxxxx
    scope: Route
    resource_ids: [route-xxxxxxxx]
    enabled: true
"""
RETURN = r"""waf_protection: {description: Effective WAF state for the requested scope and resources., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def describe_request(models, p):
    r = models.DescribeWafProtectionRequest()
    r.GatewayId, r.Type, r.TypeList = p["gateway_id"], p["scope"], [p["scope"]]
    return r


def mutation_request(cls, p, resource_ids):
    r = cls()
    r.GatewayId, r.Type, r.List = p["gateway_id"], p["scope"], resource_ids or None
    return r


def enabled_value(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "on", "open", "opened", "enable", "enabled")


def status_map(result, scope):
    if scope == "Global":
        return {"Global": enabled_value(result.get("GlobalStatus"))}
    field = "ServicesStatus" if scope == "Service" else "RouteStatus"
    return {item.get("Id"): enabled_value(item.get("Status")) for item in result.get(field) or [] if item.get("Id")}


def current(module, client, models, p):
    result = module.sdk_call(client.DescribeWafProtection, describe_request(models, p)).Result
    return status_map(result._serialize(allow_none=True) if result else {}, p["scope"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "gateway_id": {"required": True},
            "scope": {"choices": ["Global", "Service", "Route"], "required": True},
            "resource_ids": {"type": "list", "elements": "str"},
            "enabled": {"type": "bool", "required": True},
        },
        supports_check_mode=True,
    )
    p = module.params
    ids = p.get("resource_ids") or []
    if p["scope"] == "Global" and ids:
        module.fail_json(msg="resource_ids must be empty for Global WAF protection")
    if p["scope"] != "Global" and not ids:
        module.fail_json(msg="resource_ids is required for Service or Route WAF protection")
    if len(set(ids)) != len(ids):
        module.fail_json(msg="resource_ids must not contain duplicates")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        before = current(module, client, models, p)
        requested = ["Global"] if p["scope"] == "Global" else ids
        missing = [item for item in requested if before.get(item, False) != p["enabled"]]
        target = {item: p["enabled"] for item in requested}
        if not missing:
            module.exit_json(changed=False, waf_protection={"Scope": p["scope"], "Status": target})
        diff = maybe_diff(module, {item: before.get(item, False) for item in requested}, target)
        if not module.check_mode:
            if p["enabled"]:
                api, cls = client.OpenWafProtection, models.OpenWafProtectionRequest
            else:
                api, cls = client.CloseWafProtection, models.CloseWafProtectionRequest
            module.sdk_call(api, mutation_request(cls, p, [] if p["scope"] == "Global" else missing))
            effective = current(module, client, models, p)
        else:
            effective = target
        module.exit_json(
            changed=True,
            **(diff or {}),
            waf_protection={"Scope": p["scope"], "Status": {item: effective.get(item, p["enabled"]) for item in requested}, "AffectedResourceIds": missing},
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
