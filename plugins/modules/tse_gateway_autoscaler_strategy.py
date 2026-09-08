#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_autoscaler_strategy
short_description: Manage a Tencent Cloud TSE gateway autoscaler strategy
version_added: "0.14.0"
description: Creates, updates and deletes metric- and cron-based gateway autoscaling strategies.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  strategy_id: {type: str, description: Existing strategy ID.}
  name: {type: str, description: Instance-unique strategy name.}
  description: {type: str, description: Strategy description.}
  metric_config: {type: dict, description: SDK CloudNativeAPIGatewayStrategyAutoScalerConfig payload.}
  cron_config: {type: dict, description: SDK CloudNativeAPIGatewayStrategyCronScalerConfig payload.}
  max_replicas: {type: int, description: Maximum gateway nodes.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_autoscaler_strategy:
    gateway_id: gateway-xxxxxxxx
    name: production-elasticity
    max_replicas: 10
    metric_config:
      Enabled: true
      MaxReplicas: 10
      Metrics: [{Type: Resource, ResourceName: cpu, TargetType: Utilization, TargetValue: 60}]
    cron_config:
      Enabled: true
      Params: [{Period: daily, StartAt: '09:00', TargetReplicas: 4}]
"""
RETURN = r"""strategy: {description: Effective autoscaling strategy., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def json_request(cls, payload):
    r = cls()
    r.from_json_string(json.dumps(payload))
    return r


def describe_request(models, p, strategy_id=None):
    r = models.DescribeAutoScalerResourceStrategiesRequest()
    r.GatewayId, r.StrategyId = p["gateway_id"], strategy_id
    return r


def delete_request(models, p, current):
    r = models.DeleteAutoScalerResourceStrategyRequest()
    r.GatewayId, r.StrategyId = p["gateway_id"], current["StrategyId"]
    return r


def target(p, current=None):
    current = current or {}
    return {
        "StrategyName": p.get("name") or current.get("StrategyName"),
        "Description": p.get("description") if p.get("description") is not None else current.get("Description"),
        "Config": p.get("metric_config") if p.get("metric_config") is not None else current.get("Config"),
        "CronConfig": p.get("cron_config") if p.get("cron_config") is not None else current.get("CronConfig"),
        "MaxReplicas": p.get("max_replicas") if p.get("max_replicas") is not None else current.get("MaxReplicas"),
    }


def mutation_payload(p, current=None):
    payload = dict({"GatewayId": p["gateway_id"]}, **target(p, current))
    if current:
        payload["StrategyId"] = current["StrategyId"]
    return payload


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    return actual == expected


def find(module, client, models, p):
    result = module.sdk_call(client.DescribeAutoScalerResourceStrategies, describe_request(models, p, p.get("strategy_id"))).Result
    values = result.StrategyList if result else []
    matches = []
    for item in values or []:
        value = item._serialize(allow_none=True)
        if (p.get("strategy_id") and value.get("StrategyId") == p["strategy_id"]) or (not p.get("strategy_id") and value.get("StrategyName") == p["name"]):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE autoscaler strategies matched; specify strategy_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "gateway_id": {"required": True},
            "strategy_id": {},
            "name": {},
            "description": {},
            "metric_config": {"type": "dict"},
            "cron_config": {"type": "dict"},
            "max_replicas": {"type": "int"},
        },
        required_one_of=[("strategy_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, strategy=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteAutoScalerResourceStrategy, delete_request(models, p, current))
            module.exit_json(changed=True, **(diff or {}), strategy=None)
        if not current and not p.get("name"):
            module.fail_json(msg="name is required for a new TSE autoscaler strategy")
        desired = target(p, current)
        before = {key: (current or {}).get(key) for key in desired}
        if current and contains(before, desired):
            module.exit_json(changed=False, strategy=current)
        diff = maybe_diff(module, before if current else None, desired)
        if not module.check_mode:
            if current:
                module.sdk_call(
                    client.ModifyAutoScalerResourceStrategy, json_request(models.ModifyAutoScalerResourceStrategyRequest, mutation_payload(p, current))
                )
            else:
                response = module.sdk_call(
                    client.CreateAutoScalerResourceStrategy, json_request(models.CreateAutoScalerResourceStrategyRequest, mutation_payload(p))
                )
                p["strategy_id"] = response.StrategyId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), strategy=current if not module.check_mode else desired)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
