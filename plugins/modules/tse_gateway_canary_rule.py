#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_canary_rule
short_description: Manage a Tencent Cloud TSE gateway canary rule
version_added: "0.14.0"
description:
  - Creates, updates and deletes a priority-addressed canary rule for one gateway service.
  - C(config) accepts the SDK CloudNativeAPIGatewayCanaryRule shape; C(Priority) is supplied from the stable module identity.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  gateway_id:
    description:
      - Gateway the canary rule applies to.
    type: str
    required: true
  service_id:
    description:
      - Owning service ID.
    type: str
    required: true
  priority:
    description:
      - Unique rule priority from 0 through 100.
    type: int
    required: true
  rule_type:
    description:
      - Rule category used for lookup.
    type: str
    choices: [Standard, Lane]
    default: Standard
  config:
    description:
      - SDK CloudNativeAPIGatewayCanaryRule payload excluding Priority.
    type: dict

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_canary_rule:
    gateway_id: gateway-xxxxxxxx
    service_id: service-xxxxxxxx
    priority: 90
    config:
      Enabled: true
      ConditionList:
        - {Type: header, Key: X-Canary, Operator: exact, Value: beta}
      BalancedServiceList:
        - {ServiceID: service-stable, Percent: 90}
        - {ServiceID: service-canary, Percent: 10}

- name: Delete the canary rule
  susunola.tencentcloud.tse_gateway_canary_rule:
    state: absent
    gateway_id: gateway-xxxxxxxx
    priority: 90
    service_id: service-xxxxxxxx
"""
RETURN = r"""canary_rule:
  description:
    - Effective canary rule.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    Priority: 90
    RuleType: Standard
    Enabled: true
    ConditionList:
      - Type: header
        Key: X-Canary
        Operator: exact
        Value: beta
    BalancedServiceList:
      - ServiceID: service-stable
        Percent: 90
      - ServiceID: service-canary
        Percent: 10
    GatewayId: gateway-abc
    ServiceId: service-orders
    CreateTime: '2026-01-01'
"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def list_request(models, p, offset=0):
    r = models.DescribeCloudNativeAPIGatewayCanaryRulesRequest()
    r.GatewayId, r.ServiceId, r.RuleType, r.Offset, r.Limit = p["gateway_id"], p["service_id"], p["rule_type"], offset, 20
    return r


def mutation_request(cls, p, config=None):
    payload = {"GatewayId": p["gateway_id"], "ServiceId": p["service_id"]}
    if config is None:
        payload["Priority"] = p["priority"]
    else:
        payload["Priority"] = p["priority"]
        payload["CanaryRule"] = dict(config, Priority=p["priority"])
    r = cls()
    r.from_json_string(json.dumps(payload))
    return r


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return actual == expected
    return actual == expected


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        result = module.sdk_call(client.DescribeCloudNativeAPIGatewayCanaryRules, list_request(models, p, offset)).Result
        values = result.CanaryRuleList if result else []
        for item in values or []:
            value = item._serialize(allow_none=True)
            if int(value.get("Priority")) == p["priority"]:
                matches.append(value)
        offset += len(values or [])
        total = int(result.TotalCount or 0) if result else 0
        if not result or offset >= total:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE canary rules matched the same service and priority")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "gateway_id": {"required": True},
            "service_id": {"required": True},
            "priority": {"type": "int", "required": True},
            "rule_type": {"choices": ["Standard", "Lane"], "default": "Standard"},
            "config": {"type": "dict"},
        },
        required_if=[("state", "present", ("config",))],
        supports_check_mode=True,
    )
    p = module.params
    if not 0 <= p["priority"] <= 100:
        module.fail_json(msg="priority must be between 0 and 100")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, canary_rule=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCloudNativeAPIGatewayCanaryRule, mutation_request(models.DeleteCloudNativeAPIGatewayCanaryRuleRequest, p))
            module.exit_json(changed=True, **(diff or {}), canary_rule=None)
        target = dict(p["config"], Priority=p["priority"])
        if target.get("RuleType") and target["RuleType"] != p["rule_type"]:
            module.fail_json(msg="config.RuleType must match rule_type")
        target.setdefault("RuleType", p["rule_type"])
        if current and contains(current, target):
            module.exit_json(changed=False, canary_rule=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            cls = models.ModifyCloudNativeAPIGatewayCanaryRuleRequest if current else models.CreateCloudNativeAPIGatewayCanaryRuleRequest
            api = client.ModifyCloudNativeAPIGatewayCanaryRule if current else client.CreateCloudNativeAPIGatewayCanaryRule
            module.sdk_call(api, mutation_request(cls, p, target))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), canary_rule=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
