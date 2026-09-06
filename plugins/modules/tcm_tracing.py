#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tcm_tracing
short_description: Manage Tencent Cloud Mesh tracing
version_added: "0.14.0"
description: Reconciles distributed tracing, sampling and APM or Zipkin destinations for a TCM mesh.
options:
  mesh_id: {type: str, required: true, description: TCM mesh ID.}
  enabled: {type: bool, default: true, description: Enable distributed tracing.}
  sampling: {type: float, default: 1.0, description: Trace sampling value accepted by TCM.}
  apm: {type: dict, description: SDK APM destination payload.}
  zipkin: {type: dict, description: SDK TracingZipkin payload.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  waiter_delay: {type: int, default: 5, description: Polling interval.}
  waiter_timeout: {type: int, default: 120, description: Convergence timeout.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tcm_tracing:
    mesh_id: mesh-xxxxxxxx
    enabled: true
    sampling: 1.0
    apm: {Enable: true}
"""
RETURN = r"""tracing: {description: Effective TCM tracing configuration., type: dict, returned: always}"""
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
    request = models.DescribeMeshRequest()
    request.MeshId = mesh_id
    return request


def update_request(models, p):
    request = models.ModifyTracingConfigRequest()
    request.MeshId, request.Enable, request.Sampling = p["mesh_id"], p["enabled"], p["sampling"]
    request.APM, request.Zipkin = model(models.APM, p.get("apm")), model(models.TracingZipkin, p.get("zipkin"))
    return request


def desired(p):
    value = {"Enable": p["enabled"], "Sampling": p["sampling"]}
    if p["enabled"]:
        if p.get("apm") is not None:
            value["APM"] = p["apm"]
        if p.get("zipkin") is not None:
            value["Zipkin"] = p["zipkin"]
    return value


def current(module, client, models, mesh_id):
    mesh = module.sdk_call(client.DescribeMesh, describe_request(models, mesh_id)).Mesh
    if not mesh:
        module.fail_json(msg="TCM mesh was not found", mesh_id=mesh_id)
    value = mesh._serialize(allow_none=True).get("Config") or {}
    return value.get("Tracing") or {"Enable": False, "Sampling": 0.0, "APM": None, "Zipkin": None}


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    return actual == expected


def normalized(value):
    result = dict(value or {})
    result["Enable"] = bool(result.get("Enable"))
    result["Sampling"] = float(result.get("Sampling") or 0)
    return result


def converged(value, target):
    return contains(normalized(value), target)


def wait(module, client, models, target):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        value = current(module, client, models, module.params["mesh_id"])
        if converged(value, target):
            return value
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TCM tracing convergence", tracing=value, expected=target)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "mesh_id": {"required": True},
            "enabled": {"type": "bool", "default": True},
            "sampling": {"type": "float", "default": 1.0},
            "apm": {"type": "dict"},
            "zipkin": {"type": "dict"},
        },
        mutually_exclusive=[("apm", "zipkin")],
        supports_check_mode=True,
    )
    p = module.params
    if p["sampling"] < 0 or p["sampling"] > 100:
        module.fail_json(msg="sampling must be between 0 and 100 percent")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TcmClient, "tcm.tencentcloudapi.com")
    try:
        before_value = current(module, client, models, p["mesh_id"])
        before, target = normalized(before_value), desired(p)
        if converged(before_value, target):
            module.exit_json(changed=False, tracing=before_value)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyTracingConfig, update_request(models, p))
            before_value = wait(module, client, models, target)
        module.exit_json(changed=True, **(diff or {}), tracing=before_value if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
