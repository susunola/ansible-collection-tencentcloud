#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_governance_instance
short_description: Manage a Tencent Cloud TSE governance service instance
version_added: "0.14.0"
description: Registers, updates and removes a service instance using namespace, service, host and port identity. Supply governance_instance_id when changing identity fields.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
  governance_instance_id: {type: str, description: Existing governance service instance ID.}
  namespace: {type: str, required: true, description: Service namespace.}
  service: {type: str, required: true, description: Service name.}
  host: {type: str, required: true, description: Instance host or IP.}
  port: {type: int, required: true, description: Instance listening port.}
  protocol: {type: str, description: Instance protocol.}
  instance_version: {type: str, description: Application version.}
  weight: {type: int, description: Load-balancing weight.}
  healthy: {type: bool, description: Administrative health state.}
  isolate: {type: bool, description: Isolation state.}
  enable_health_check: {type: bool, description: Enable heartbeat health checks.}
  ttl: {type: int, description: Heartbeat TTL in seconds.}
  metadata: {type: list, elements: dict, description: Authoritative SDK Metadata list.}
  waiter_delay: {type: int, default: 2, description: Reconciliation polling interval.}
  waiter_timeout: {type: int, default: 60, description: Reconciliation timeout.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_governance_instance:
    instance_id: ins-xxxxxxxx
    namespace: production
    service: orders
    host: 10.0.0.30
    port: 8080
    protocol: http
    weight: 100
    enable_health_check: true
    ttl: 5
"""
RETURN = r"""governance_instance: {description: Effective governance service instance metadata., type: dict, returned: always}"""
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def describe_request(models, p, offset=0):
    r = models.DescribeGovernanceInstancesRequest()
    r.InstanceId, r.Namespace, r.Service, r.Host, r.Offset, r.Limit = (
        p["instance_id"],
        p["namespace"],
        p["service"],
        None if p.get("governance_instance_id") else p["host"],
        offset,
        100,
    )
    return r


def model(cls, value):
    r = cls()
    r.from_json_string(json.dumps(value))
    return r


def request(cls, models, p, value, update=False):
    r = cls()
    r.InstanceId = p["instance_id"]
    item = model(models.GovernanceInstanceUpdate if update else models.GovernanceInstanceInput, value)
    r.GovernanceInstances = [item]
    return r


def delete_request(models, p, current):
    return request(
        models.DeleteGovernanceInstancesRequest,
        models,
        p,
        {"Id": current["Id"], "Service": current["Service"], "Namespace": current["Namespace"], "Host": current["Host"], "Port": current["Port"]},
        True,
    )


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        unmatched = list(actual)
        for item in expected:
            index = next((i for i, candidate in enumerate(unmatched) if contains(candidate, item)), None)
            if index is None:
                return False
            unmatched.pop(index)
        return True
    return actual == expected


def desired(p, current=None):
    value = {"Service": p["service"], "Namespace": p["namespace"], "Host": p["host"], "Port": p["port"]}
    mapping = (
        ("protocol", "Protocol"),
        ("instance_version", "InstanceVersion"),
        ("weight", "Weight"),
        ("healthy", "Healthy"),
        ("isolate", "Isolate"),
        ("enable_health_check", "EnableHealthCheck"),
        ("ttl", "Ttl"),
        ("metadata", "Metadatas"),
    )
    for source, target in mapping:
        selected = p.get(source) if p.get(source) is not None else (current or {}).get(target)
        if selected is not None:
            value[target] = selected
    if current and current.get("Id"):
        value["Id"] = current["Id"]
    return value


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeGovernanceInstances, describe_request(models, p, offset))
        page = response.Content or []
        for item in page:
            value = item._serialize(allow_none=True)
            identity = (
                value.get("Namespace") == p["namespace"]
                and value.get("Service") == p["service"]
                and value.get("Host") == p["host"]
                and value.get("Port") == p["port"]
            )
            if (p.get("governance_instance_id") and value.get("Id") == p["governance_instance_id"]) or (not p.get("governance_instance_id") and identity):
                matches.append(value)
        offset += len(page)
        if offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE governance service instances matched; specify governance_instance_id")
    return matches[0] if matches else None


def wait(module, client, models, p, target=None, absent=False):
    deadline = time.time() + p["waiter_timeout"]
    while True:
        value = find(module, client, models, p)
        if absent and value is None:
            return None
        if not absent and value is not None and contains(value, target or {}):
            return value
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TSE governance service instance convergence", governance_instance=value)
        time.sleep(p["waiter_delay"])


def require_success(module, response, operation):
    if getattr(response, "Result", None) is not True:
        module.fail_json(msg="TSE governance service instance operation returned an unsuccessful result", operation=operation)


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {"required": True},
        "governance_instance_id": {},
        "namespace": {"required": True},
        "service": {"required": True},
        "host": {"required": True},
        "port": {"type": "int", "required": True},
        "protocol": {},
        "instance_version": {},
        "weight": {"type": "int"},
        "healthy": {"type": "bool"},
        "isolate": {"type": "bool"},
        "enable_health_check": {"type": "bool"},
        "ttl": {"type": "int"},
        "metadata": {"type": "list", "elements": "dict"},
        "waiter_delay": {"type": "int", "default": 2},
        "waiter_timeout": {"type": "int", "default": 60},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, governance_instance=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                require_success(module, module.sdk_call(client.DeleteGovernanceInstances, delete_request(models, p, current)), "DeleteGovernanceInstances")
                wait(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff or {}), governance_instance=None)
        target = desired(p, current)
        if current and contains(current, target):
            module.exit_json(changed=False, governance_instance=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if not current:
                create_target = {key: value for key, value in target.items() if key != "Metadatas"}
                require_success(
                    module,
                    module.sdk_call(client.CreateGovernanceInstances, request(models.CreateGovernanceInstancesRequest, models, p, create_target)),
                    "CreateGovernanceInstances",
                )
                current = wait(module, client, models, p, create_target)
                target = desired(p, current)
            if not contains(current, target):
                require_success(
                    module,
                    module.sdk_call(client.ModifyGovernanceInstances, request(models.ModifyGovernanceInstancesRequest, models, p, target, True)),
                    "ModifyGovernanceInstances",
                )
                current = wait(module, client, models, dict(p, governance_instance_id=current["Id"]), target)
        module.exit_json(changed=True, **(diff or {}), governance_instance=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
