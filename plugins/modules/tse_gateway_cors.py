#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_cors
short_description: Manage CORS policy on a Tencent Cloud TSE gateway resource
version_added: "0.14.0"
description: Creates, updates and deletes the CORS plugin bound to one gateway service or route.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  scope: {type: str, choices: [service, route], required: true, description: Bound resource type.}
  resource_id: {type: str, required: true, description: Service or route ID.}
  enabled: {type: bool, description: Whether the plugin is enabled; creation defaults to true.}
  origins: {type: list, elements: str, description: Allowed origins.}
  headers: {type: list, elements: str, description: Allowed request headers.}
  methods: {type: list, elements: str, description: Allowed methods.}
  exposed_headers: {type: list, elements: str, description: Response headers exposed to browsers.}
  max_age: {type: int, description: Preflight cache duration in seconds.}
  credentials: {type: bool, description: Allow credentialed cross-origin requests.}
  preflight_continue: {type: bool, description: Forward OPTIONS requests upstream.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_cors:
    gateway_id: gateway-xxxxxxxx
    scope: route
    resource_id: route-xxxxxxxx
    origins: ['https://app.example.com']
    methods: [GET, POST]
    credentials: true
"""
RETURN = r"""cors: {description: Effective CORS policy., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


FIELDS = {
    "enabled": "Enabled",
    "origins": "Origins",
    "headers": "Headers",
    "methods": "Methods",
    "exposed_headers": "ExposedHeaders",
    "max_age": "MaxAge",
    "credentials": "Credentials",
    "preflight_continue": "PreFlightContinue",
}
DEFAULTS = {"Enabled": True, "Origins": [], "Headers": [], "Methods": [], "ExposedHeaders": [], "MaxAge": 0, "Credentials": False, "PreFlightContinue": False}


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
    response = module.sdk_call(client.DescribeCloudNativeAPIGatewayCORS, request(models.DescribeCloudNativeAPIGatewayCORSRequest, p))
    result = response.Result
    return result._serialize(allow_none=True) if result else None


def target_config(p, current):
    return {
        field: (p[source] if p.get(source) is not None else ((current or {}).get(field, default)))
        for source, field in FIELDS.items()
        for default in [DEFAULTS[field]]
    }


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "gateway_id": {"required": True},
        "scope": {"choices": ["service", "route"], "required": True},
        "resource_id": {"required": True},
        "enabled": {"type": "bool"},
        "origins": {"type": "list", "elements": "str"},
        "headers": {"type": "list", "elements": "str"},
        "methods": {"type": "list", "elements": "str"},
        "exposed_headers": {"type": "list", "elements": "str"},
        "max_age": {"type": "int"},
        "credentials": {"type": "bool"},
        "preflight_continue": {"type": "bool"},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = get_current(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, cors=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCloudNativeAPIGatewayCORS, request(models.DeleteCloudNativeAPIGatewayCORSRequest, p))
            module.exit_json(changed=True, **(diff or {}), cors=None)
        target = target_config(p, current)
        before = {key: (current or {}).get(key) for key in target}
        if current and before == target:
            module.exit_json(changed=False, cors=current)
        diff = maybe_diff(module, before if current else None, target)
        if not module.check_mode:
            module.sdk_call(client.CreateOrModifyCloudNativeAPIGatewayCORS, request(models.CreateOrModifyCloudNativeAPIGatewayCORSRequest, p, target))
            current = get_current(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), cors=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
