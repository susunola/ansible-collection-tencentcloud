#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tcm_prometheus
short_description: Manage Tencent Cloud Mesh Prometheus integration
version_added: "0.14.0"
description: Links, reconciles or unlinks Tencent Cloud or third-party Prometheus from a TCM mesh.
options:
  mesh_id: {type: str, required: true, description: TCM mesh ID.}
  state: {type: str, choices: [present, absent], default: present, description: Desired integration state.}
  config: {type: dict, no_log: true, description: SDK PrometheusConfig payload, including optional CustomProm credentials.}
  rotate_credentials: {type: bool, default: false, description: Force relinking when write-only credentials must be rotated.}

  waiter_delay: {type: int, default: 5, description: Polling interval.}
  waiter_timeout: {type: int, default: 180, description: Convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tcm_prometheus:
    mesh_id: mesh-xxxxxxxx
    config:
      Region: ap-guangzhou
      InstanceId: prom-xxxxxxxx

- susunola.tencentcloud.tcm_prometheus:
    mesh_id: mesh-xxxxxxxx
    state: absent
"""
RETURN = r"""prometheus: {description: Effective Prometheus configuration with secrets redacted., type: dict, returned: always}"""
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tcm.v20210413 import models, tcm_client

    return models, tcm_client


def model(cls, value):
    result = cls()
    result.from_json_string(json.dumps(value))
    return result


def describe_request(models, mesh_id):
    request = models.DescribeMeshRequest()
    request.MeshId = mesh_id
    return request


def link_request(models, mesh_id, config):
    request = models.LinkPrometheusRequest()
    request.MeshID, request.Prometheus = mesh_id, model(models.PrometheusConfig, config)
    return request


def unlink_request(models, mesh_id):
    request = models.UnlinkPrometheusRequest()
    request.MeshID = mesh_id
    return request


def current(module, client, models, mesh_id):
    mesh = module.sdk_call(client.DescribeMesh, describe_request(models, mesh_id)).Mesh
    if not mesh:
        module.fail_json(msg="TCM mesh was not found", mesh_id=mesh_id)
    config = mesh._serialize(allow_none=True).get("Config") or {}
    return config.get("Prometheus")


def without_secrets(value):
    if isinstance(value, dict):
        return {key: without_secrets(item) for key, item in value.items() if key.lower() not in ("password", "secret", "token")}
    if isinstance(value, list):
        return [without_secrets(item) for item in value]
    return value


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    return actual == expected


def converged(value, target):
    return bool(value) and contains(without_secrets(value), without_secrets(target))


def wait(module, client, models, target):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        value = current(module, client, models, module.params["mesh_id"])
        if (target is None and not value) or (target is not None and converged(value, target)):
            return value
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TCM Prometheus convergence", prometheus=without_secrets(value), expected=without_secrets(target))
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "mesh_id": {"required": True},
            "state": {"choices": ["present", "absent"], "default": "present"},
            "config": {"type": "dict", "no_log": True},
            "rotate_credentials": {"type": "bool", "default": False},
        },
        required_if=[("state", "present", ("config",))],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TcmClient, "tcm.tencentcloudapi.com")
    try:
        before_value = current(module, client, models, p["mesh_id"])
        before = without_secrets(before_value)
        if p["state"] == "absent":
            if not before_value:
                module.exit_json(changed=False, prometheus=None)
            diff = maybe_diff(module, before, None)
            if not module.check_mode:
                module.sdk_call(client.UnlinkPrometheus, unlink_request(models, p["mesh_id"]))
                before_value = wait(module, client, models, None)
            module.exit_json(changed=True, **(diff or {}), prometheus=None)
        target = p["config"]
        if converged(before_value, target) and not p["rotate_credentials"]:
            module.exit_json(changed=False, prometheus=before)
        safe_target = without_secrets(target)
        diff = maybe_diff(module, before, safe_target)
        if not module.check_mode:
            module.sdk_call(client.LinkPrometheus, link_request(models, p["mesh_id"], target))
            before_value = wait(module, client, models, target)
        module.exit_json(changed=True, **(diff or {}), prometheus=without_secrets(before_value) if not module.check_mode else safe_target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
