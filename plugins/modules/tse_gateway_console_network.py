#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_gateway_console_network
short_description: Manage Tencent Cloud TSE gateway console network access
version_added: "0.14.0"
description: Opens or closes the Konga console network, reconciles access control and waits for network state convergence.
options:
  gateway_id: {type: str, required: true, description: Cloud-native API gateway ID.}
  state: {type: str, choices: [open, closed], default: open, description: Desired console network state.}
  network_type: {type: str, choices: [Open], default: Open, description: Console network type supported by Tencent Cloud.}
  access_control: {type: dict, description: Exact SDK NetworkAccessControl payload used when opening the console.}
  waiter_delay: {type: int, default: 5, description: Polling interval while waiting for convergence.}
  waiter_timeout: {type: int, default: 600, description: Maximum convergence wait.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_gateway_console_network:
    gateway_id: gateway-xxxxxxxx
    state: open
    access_control:
      Mode: Whitelist
      CidrWhiteList: [203.0.113.0/24]
'''
RETURN = r'''
console_network: {description: Effective console network metadata with credential fields removed., type: dict, returned: always}
'''

import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client
    return models, tse_client


def describe_request(models, gateway_id):
    value = models.DescribeCloudNativeAPIGatewayConfigRequest()
    value.GatewayId = gateway_id
    return value


def modify_request(models, params):
    value = models.ModifyConsoleNetworkRequest()
    value.GatewayId, value.NetworkType = params["gateway_id"], params["network_type"]
    value.Operate = "Open" if params["state"] == "open" else "Close"
    if params.get("access_control") is not None:
        access = models.NetworkAccessControl()
        access.from_json_string(json.dumps(params["access_control"]))
        value.AccessControl = access
    return value


def readable(value):
    result = dict(value or {})
    result.pop("AdminPassword", None)
    return result


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return sorted(actual or []) == sorted(expected)
    return actual == expected


def find(module, client, models, params):
    response = module.sdk_call(client.DescribeCloudNativeAPIGatewayConfig,
                               describe_request(models, params["gateway_id"]))
    result = response.Result
    values = [readable(item._serialize(allow_none=True)) for item in ((result.ConfigList if result else None) or [])]
    matches = [value for value in values if str(value.get("ConsoleType") or "").lower() == "konga"]
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE Konga console network configurations were returned")
    return matches[0] if matches else None


def desired(params):
    value = {"NetType": params["network_type"], "Status": "Open" if params["state"] == "open" else "Closed"}
    if params["state"] == "open" and params.get("access_control") is not None:
        value["AccessControl"] = params["access_control"]
    return value


def wait(module, client, models, params, target):
    deadline = time.time() + params["waiter_timeout"]
    while True:
        current = find(module, client, models, params)
        if current is not None and contains(current, target):
            return current
        if current and str(current.get("Status") or "").lower() in ("failed", "error"):
            module.fail_json(msg="TSE gateway console network operation failed", console_network=current)
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TSE gateway console network convergence",
                             console_network=current, expected=target)
        time.sleep(params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={
        "gateway_id": {"required": True}, "state": {"choices": ["open", "closed"], "default": "open"},
        "network_type": {"choices": ["Open"], "default": "Open"}, "access_control": {"type": "dict"},
        "waiter_delay": {"type": "int", "default": 5}, "waiter_timeout": {"type": "int", "default": 600},
    }, supports_check_mode=True)
    params = module.params
    if params["state"] == "closed" and params.get("access_control") is not None:
        module.fail_json(msg="access_control is only valid when state=open")
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TseClient, "tse.tencentcloudapi.com")
    try:
        current, target = find(module, client, models, params), desired(params)
        if current is not None and contains(current, target):
            module.exit_json(changed=False, console_network=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyConsoleNetwork, modify_request(models, params))
            current = wait(module, client, models, params, target)
        else:
            current = target
        module.exit_json(changed=True, **(diff or {}), console_network=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
