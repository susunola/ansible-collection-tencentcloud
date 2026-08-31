#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: emr_auto_scale_strategy
short_description: Manage Tencent Cloud EMR automatic scaling strategies
version_added: "0.14.0"
description:
  - Reconciles one named load-based or time-based automatic scaling strategy.
  - Deletion requires explicit authorization because EMR also destroys nodes created by the rule.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, required: true, description: EMR cluster ID.}
  group_id: {type: int, description: EMR scaling group ID.}
  strategy_type: {type: str, choices: [load, time], required: true, description: Scaling strategy type.}
  name: {type: str, required: true, description: Unique strategy name in the cluster.}
  strategy: {type: dict, description: SDK LoadAutoScaleStrategy or TimeAutoScaleStrategy fields.}
  allow_node_termination: {type: bool, default: false, description: Authorize deletion and its associated scaled-node termination.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.emr_auto_scale_strategy:
    cluster_id: emr-xxxxxxxx
    group_id: 2
    strategy_type: load
    name: scale-task-on-yarn-pressure
    strategy:
      ScaleAction: 1
      ScaleNum: 2
      StrategyStatus: 1
      CalmDownTime: 300
      LoadMetricsConditions: {LoadMetrics: []}
'''
RETURN = r'''strategy: {description: Effective automatic scaling strategy., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import changed, maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.emr.v20190103 import models, emr_client
    return models, emr_client


def describe(module, client, models, cluster_id, group_id, strategy_type):
    request = models.DescribeAutoScaleStrategiesRequest()
    request.InstanceId, request.GroupId = cluster_id, group_id
    response = module.sdk_call(client.DescribeAutoScaleStrategies, request)
    values = response.LoadAutoScaleStrategies if strategy_type == "load" else response.TimeBasedAutoScaleStrategies
    return [item._serialize(allow_none=True) for item in (values or [])]


def find(values, name):
    matches = [item for item in values if item.get("StrategyName") == name]
    if len(matches) > 1:
        raise ValueError("Multiple EMR auto scaling strategies have the requested name")
    return matches[0] if matches else None


def wanted(params):
    value = dict(params.get("strategy") or {})
    value["StrategyName"] = params["name"]
    if params.get("group_id") is not None:
        value["GroupId"] = params["group_id"]
    return value


def subset(current, target):
    return {key: current.get(key) for key in target}


def add(module, client, models, params, target):
    payload = {"InstanceId": params["cluster_id"], "StrategyType": 1 if params["strategy_type"] == "load" else 2}
    payload["LoadAutoScaleStrategy" if params["strategy_type"] == "load" else "TimeAutoScaleStrategy"] = target
    request = models.AddMetricScaleStrategyRequest(); request._deserialize(payload)
    module.sdk_call(client.AddMetricScaleStrategy, request)


def update(module, client, models, params, values, current, target):
    replacement = dict(target); replacement["StrategyId"] = current.get("StrategyId")
    merged = [replacement if item.get("StrategyName") == params["name"] else item for item in values]
    payload = {"InstanceId": params["cluster_id"], "GroupId": params.get("group_id"),
               "StrategyType": 1 if params["strategy_type"] == "load" else 2}
    payload["LoadAutoScaleStrategies" if params["strategy_type"] == "load" else "TimeAutoScaleStrategies"] = merged
    request = models.ModifyAutoScaleStrategyRequest(); request._deserialize(payload)
    module.sdk_call(client.ModifyAutoScaleStrategy, request)


def delete(module, client, models, params, current):
    request = models.DeleteAutoScaleStrategyRequest()
    request.InstanceId, request.GroupId = params["cluster_id"], params.get("group_id")
    request.StrategyType = 1 if params["strategy_type"] == "load" else 2
    request.StrategyId = current["StrategyId"]
    module.sdk_call(client.DeleteAutoScaleStrategy, request)


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"},
        "cluster_id": {"required": True}, "group_id": {"type": "int"},
        "strategy_type": {"choices": ["load", "time"], "required": True},
        "name": {"required": True}, "strategy": {"type": "dict"},
        "allow_node_termination": {"type": "bool", "default": False},
    }, required_if=[("state", "present", ["strategy"])], supports_check_mode=True)
    module.require_sdk(); models, client_module = _load()
    client = module.create_client(client_module.EmrClient, "emr.tencentcloudapi.com")
    try:
        p = module.params; values = describe(module, client, models, p["cluster_id"], p.get("group_id"), p["strategy_type"])
        current = find(values, p["name"])
        if p["state"] == "absent":
            if current is None: module.exit_json(changed=False, strategy=None)
            if not p["allow_node_termination"]: module.fail_json(msg="allow_node_termination=true is required to delete an EMR scaling strategy", strategy=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: delete(module, client, models, p, current)
            module.exit_json(changed=True, **(diff or {}), strategy=current if module.check_mode else None)
        target = wanted(p)
        if current is not None and not changed(subset(current, target), target): module.exit_json(changed=False, strategy=current)
        diff = maybe_diff(module, subset(current, target) if current else None, target)
        if not module.check_mode:
            if current is None: add(module, client, models, p, target)
            else: update(module, client, models, p, values, current, target)
            current = find(describe(module, client, models, p["cluster_id"], p.get("group_id"), p["strategy_type"]), p["name"])
        module.exit_json(changed=True, **(diff or {}), strategy=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
