#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tcm_access_log
short_description: Manage Tencent Cloud Mesh access logging
version_added: "0.14.0"
description: Reconciles access-log collection, encoding and destinations for a TCM mesh.
options:
  mesh_id: {type: str, required: true, description: TCM mesh ID.}
  enabled: {type: bool, default: true, description: Enable access-log collection.}
  selected_range: {type: dict, description: SDK SelectedRange payload.}
  template: {type: str, choices: [istio, trace, custom], default: istio, description: Access-log template.}
  encoding: {type: str, choices: [TEXT, JSON], default: TEXT, description: Output encoding.}
  format: {type: str, description: Custom access-log format.}
  cls: {type: dict, description: SDK CLS destination payload.}
  enable_stdout: {type: bool, default: true, description: Send logs to standard output.}
  enable_server: {type: bool, default: false, description: Send logs to a third-party gRPC server.}
  server_address: {type: str, description: Third-party gRPC server address.}

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
- susunola.tencentcloud.tcm_access_log:
    mesh_id: mesh-xxxxxxxx
    enabled: true
    encoding: JSON
    enable_stdout: true
"""
RETURN = r"""access_log: {description: Effective TCM access-log configuration., type: dict, returned: always}"""
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tcm.v20210413 import models, tcm_client

    return models, tcm_client


def model(cls, value):
    if value is None:
        return None
    result = cls()
    result.from_json_string(json.dumps(value))
    return result


def describe_request(models, mesh_id):
    request = models.DescribeAccessLogConfigRequest()
    request.MeshId = mesh_id
    return request


def update_request(models, p):
    request = models.ModifyAccessLogConfigRequest()
    request.MeshId, request.Enable = p["mesh_id"], p["enabled"]
    request.SelectedRange, request.Template = model(models.SelectedRange, p.get("selected_range")), p["template"]
    request.CLS, request.Encoding, request.Format = model(models.CLS, p.get("cls")), p["encoding"], p.get("format")
    request.EnableStdout, request.EnableServer, request.Address = p["enable_stdout"], p["enable_server"], p.get("server_address")
    return request


def current(module, client, models, mesh_id):
    value = module.sdk_call(client.DescribeAccessLogConfig, describe_request(models, mesh_id))._serialize(allow_none=True)
    value.pop("RequestId", None)
    return value


def desired(p):
    return {
        "SelectedRange": p.get("selected_range"),
        "Template": p["template"],
        "Enable": p["enabled"],
        "CLS": p.get("cls"),
        "Encoding": p["encoding"],
        "Format": p.get("format"),
        "EnableStdout": p["enable_stdout"],
        "EnableServer": p["enable_server"],
        "Address": p.get("server_address"),
    }


def normalized(value):
    return {key: value.get(key) for key in ("SelectedRange", "Template", "Enable", "CLS", "Encoding", "Format", "EnableStdout", "EnableServer", "Address")}


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    return actual == expected


def converged(value, target):
    return contains(normalized(value), target)


def wait(module, client, models, target):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        value = current(module, client, models, module.params["mesh_id"])
        if converged(value, target):
            return value
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TCM access-log convergence", access_log=value, expected=target)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "mesh_id": {"required": True},
            "enabled": {"type": "bool", "default": True},
            "selected_range": {"type": "dict"},
            "template": {"choices": ["istio", "trace", "custom"], "default": "istio"},
            "encoding": {"choices": ["TEXT", "JSON"], "default": "TEXT"},
            "format": {},
            "cls": {"type": "dict"},
            "enable_stdout": {"type": "bool", "default": True},
            "enable_server": {"type": "bool", "default": False},
            "server_address": {},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["template"] == "custom" and not p.get("format"):
        module.fail_json(msg="format is required when template=custom")
    if p["enable_server"] and not p.get("server_address"):
        module.fail_json(msg="server_address is required when enable_server=true")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TcmClient, "tcm.tencentcloudapi.com")
    try:
        before_value = current(module, client, models, p["mesh_id"])
        before, target = normalized(before_value), desired(p)
        if converged(before_value, target):
            module.exit_json(changed=False, access_log=before_value)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyAccessLogConfig, update_request(models, p))
            before_value = wait(module, client, models, target)
        module.exit_json(changed=True, **(diff or {}), access_log=before_value if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
