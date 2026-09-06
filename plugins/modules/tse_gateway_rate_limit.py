#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_rate_limit
short_description: Manage Tencent Cloud TSE service or route rate limiting
version_added: "0.14.0"
description: Creates, updates and deletes a rate-limit plugin on one gateway service or route.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired plugin state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  scope: {type: str, choices: [service, route], required: true, description: Protected resource type.}
  resource: {type: str, required: true, description: Service name or ID, or route name or ID.}
  config: {type: dict, description: SDK CloudNativeAPIGatewayRateLimitDetail payload.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_rate_limit:
    gateway_id: gateway-xxxxxxxx
    scope: route
    resource: orders-api
    config:
      Enabled: true
      QpsThresholds: [{Unit: second, Max: 100}]
      LimitBy: service
"""
RETURN = r"""rate_limit: {description: Effective rate-limit configuration., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def request(cls, models, p, config=None):
    payload = {"GatewayId": p["gateway_id"], ("Name" if p["scope"] == "service" else "Id"): p["resource"]}
    if config is not None:
        payload["LimitDetail"] = config
    r = cls()
    r.from_json_string(json.dumps(payload))
    return r


def apis(client, models, scope):
    if scope == "service":
        return (
            client.DescribeCloudNativeAPIGatewayServiceRateLimit,
            client.CreateCloudNativeAPIGatewayServiceRateLimit,
            client.ModifyCloudNativeAPIGatewayServiceRateLimit,
            client.DeleteCloudNativeAPIGatewayServiceRateLimit,
            models.DescribeCloudNativeAPIGatewayServiceRateLimitRequest,
            models.CreateCloudNativeAPIGatewayServiceRateLimitRequest,
            models.ModifyCloudNativeAPIGatewayServiceRateLimitRequest,
            models.DeleteCloudNativeAPIGatewayServiceRateLimitRequest,
        )
    return (
        client.DescribeCloudNativeAPIGatewayRouteRateLimit,
        client.CreateCloudNativeAPIGatewayRouteRateLimit,
        client.ModifyCloudNativeAPIGatewayRouteRateLimit,
        client.DeleteCloudNativeAPIGatewayRouteRateLimit,
        models.DescribeCloudNativeAPIGatewayRouteRateLimitRequest,
        models.CreateCloudNativeAPIGatewayRouteRateLimitRequest,
        models.ModifyCloudNativeAPIGatewayRouteRateLimitRequest,
        models.DeleteCloudNativeAPIGatewayRouteRateLimitRequest,
    )


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    return actual == expected


def current(module, describe, describe_cls, models, p):
    try:
        response = module.sdk_call(describe, request(describe_cls, models, p))
        return response.Result._serialize(allow_none=True) if response.Result else None
    except Exception as exc:
        code = str(exc.get_code() if hasattr(exc, "get_code") else "")
        if "notfound" in code.lower() or "notexist" in code.lower():
            return None
        raise


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "gateway_id": {"required": True},
            "scope": {"choices": ["service", "route"], "required": True},
            "resource": {"required": True},
            "config": {"type": "dict"},
        },
        required_if=[("state", "present", ("config",))],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        describe, create, modify, delete, describe_cls, create_cls, modify_cls, delete_cls = apis(client, models, p["scope"])
        before = current(module, describe, describe_cls, models, p)
        if p["state"] == "absent":
            if not before:
                module.exit_json(changed=False, rate_limit=None)
            diff = maybe_diff(module, before, None)
            if not module.check_mode:
                module.sdk_call(delete, request(delete_cls, models, p))
            module.exit_json(changed=True, **(diff or {}), rate_limit=None)
        target = p["config"]
        if before and contains(before, target):
            module.exit_json(changed=False, rate_limit=before)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(modify if before else create, request(modify_cls if before else create_cls, models, p, target))
            before = current(module, describe, describe_cls, models, p)
        module.exit_json(changed=True, **(diff or {}), rate_limit=before if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
