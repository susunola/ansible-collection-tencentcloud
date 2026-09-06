#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_service_source
short_description: Manage a Tencent Cloud TSE gateway service source
version_added: "0.14.0"
description: Manages gateway integrations with registry, Kubernetes, private DNS and customer DNS service sources.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  source_id: {type: str, description: Service source ID or backing source instance ID.}
  source_name: {type: str, description: Service source name.}
  source_type: {type: str, choices: [TSE-Nacos, TSE-Consul, TSE-PolarisMesh, Customer-Nacos, Customer-Consul, Customer-PolarisMesh, TSF, TKE, EKS, PrivateDNS, Customer-DNS], description: Service source type.}
  source_info: {type: dict, no_log: true, description: SDK SourceInfo payload. Password and access-token values are write-only.}
  rotate_credentials: {type: bool, default: false, description: Force an update when write-only credentials in source_info must be rotated.}
  waiter_delay: {type: int, default: 3, description: Reconciliation polling interval.}
  waiter_timeout: {type: int, default: 180, description: Reconciliation timeout.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_service_source:
    gateway_id: gateway-xxxxxxxx
    source_name: customer-nacos
    source_type: Customer-Nacos
    source_id: nacos-instance-id
    source_info:
      Addresses: [10.0.0.20:8848]
      VpcInfo: {VpcID: vpc-xxxxxxxx, SubnetID: subnet-xxxxxxxx}
      Auth: {Username: gateway-reader, Password: "{{ vault_nacos_password }}"}
"""
RETURN = r"""source: {description: Effective service source metadata., type: dict, returned: always}"""
import copy
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


WRITE_ONLY_AUTH_FIELDS = ("Password", "AccessToken")


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def write_request(cls, p, payload):
    r = cls()
    r.from_json_string(json.dumps(payload))
    return r


def list_request(models, p):
    payload = {
        "GatewayID": p["gateway_id"],
        "Limit": 100,
        "Offset": 0,
        "SourceID": p.get("source_id"),
        "SourceName": None if p.get("source_id") else p.get("source_name"),
    }
    return write_request(models.DescribeNativeGatewayServiceSourcesRequest, p, {k: v for k, v in payload.items() if v is not None})


def create_request(models, p):
    payload = {
        "GatewayID": p["gateway_id"],
        "SourceType": p["source_type"],
        "SourceID": p.get("source_id"),
        "SourceName": p.get("source_name"),
        "SourceInfo": p.get("source_info"),
    }
    return write_request(models.CreateNativeGatewayServiceSourceRequest, p, {k: v for k, v in payload.items() if v is not None})


def update_request(models, p, current):
    payload = {
        "GatewayID": p["gateway_id"],
        "SourceID": current["SourceID"],
        "SourceName": p.get("source_name") if p.get("source_name") is not None else current.get("SourceName"),
    }
    if p.get("source_info") is not None:
        payload["SourceInfo"] = p["source_info"]
    return write_request(models.ModifyNativeGatewayServiceSourceRequest, p, payload)


def delete_request(models, p, source_id):
    return write_request(models.DeleteNativeGatewayServiceSourceRequest, p, {"GatewayID": p["gateway_id"], "SourceID": source_id})


def readable(value):
    result = copy.deepcopy(value)
    auth = (result or {}).get("SourceInfo", {}).get("Auth") if isinstance(result, dict) else None
    if isinstance(auth, dict):
        for key in WRITE_ONLY_AUTH_FIELDS:
            auth.pop(key, None)
    return result


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    return actual == expected


def desired(p):
    value = {}
    for source, target in (("source_name", "SourceName"), ("source_type", "SourceType"), ("source_info", "SourceInfo")):
        if p.get(source) is not None:
            value[target] = p[source]
    return readable(value)


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeNativeGatewayServiceSources, list_request(models, p))
    values = response.List or []
    matches = []
    for item in values:
        value = item._serialize(allow_none=True)
        if (p.get("source_id") and value.get("SourceID") == p["source_id"]) or (not p.get("source_id") and value.get("SourceName") == p.get("source_name")):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE gateway service sources matched; specify source_id")
    return matches[0] if matches else None


def wait(module, client, models, p, source_id, expected=None, absent=False):
    deadline = time.time() + p["waiter_timeout"]
    lookup = dict(p, source_id=source_id)
    while True:
        value = find(module, client, models, lookup)
        if absent and value is None:
            return None
        if not absent and value is not None and contains(readable(value), expected or {}):
            return value
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TSE gateway service source convergence", source=readable(value))
        time.sleep(p["waiter_delay"])


def require_success(module, response, operation):
    if getattr(response, "Result", None) is not True:
        module.fail_json(msg="TSE gateway service source operation returned an unsuccessful result", operation=operation)


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "gateway_id": {"required": True},
        "source_id": {},
        "source_name": {},
        "source_type": {
            "choices": [
                "TSE-Nacos",
                "TSE-Consul",
                "TSE-PolarisMesh",
                "Customer-Nacos",
                "Customer-Consul",
                "Customer-PolarisMesh",
                "TSF",
                "TKE",
                "EKS",
                "PrivateDNS",
                "Customer-DNS",
            ]
        },
        "source_info": {"type": "dict", "no_log": True},
        "rotate_credentials": {"type": "bool", "default": False},
        "waiter_delay": {"type": "int", "default": 3},
        "waiter_timeout": {"type": "int", "default": 180},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("source_id", "source_name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, source=None)
            diff = maybe_diff(module, readable(current), None)
            if not module.check_mode:
                require_success(
                    module,
                    module.sdk_call(client.DeleteNativeGatewayServiceSource, delete_request(models, p, current["SourceID"])),
                    "DeleteNativeGatewayServiceSource",
                )
                wait(module, client, models, p, current["SourceID"], absent=True)
            module.exit_json(changed=True, **(diff or {}), source=None)
        target = desired(p)
        if not current:
            missing = []
            if p.get("source_type") is None:
                missing.append("source_type")
            if p.get("source_type") != "PrivateDNS" and p.get("source_name") is None:
                missing.append("source_name")
            if p.get("source_type") not in ("PrivateDNS", "Customer-DNS") and p.get("source_id") is None:
                missing.append("source_id")
            if missing:
                module.fail_json(msg="creation parameters are required for a TSE gateway service source", missing=missing)
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                response = module.sdk_call(client.CreateNativeGatewayServiceSource, create_request(models, p))
                require_success(module, response, "CreateNativeGatewayServiceSource")
                source_id = response.SourceID or p.get("source_id")
                current = wait(module, client, models, p, source_id, target)
            module.exit_json(changed=True, **(diff or {}), source=current if not module.check_mode else target)
        if p.get("source_type") is not None and current.get("SourceType") != p["source_type"]:
            module.fail_json(msg="TSE gateway service source type is immutable", current_type=current.get("SourceType"), desired_type=p["source_type"])
        changed = not contains(readable(current), target) or p["rotate_credentials"]
        if not changed:
            module.exit_json(changed=False, source=readable(current))
        diff = maybe_diff(module, readable(current), target)
        if not module.check_mode:
            module.sdk_call(client.ModifyNativeGatewayServiceSource, update_request(models, p, current))
            current = wait(module, client, models, p, current["SourceID"], target)
        module.exit_json(changed=True, **(diff or {}), source=readable(current) if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
