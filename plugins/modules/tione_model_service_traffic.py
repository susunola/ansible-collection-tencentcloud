#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: tione_model_service_traffic
short_description: Manage Tencent Cloud TIONE service authorization and version traffic
version_added: "0.14.0"
description:
  - Reconciles a TIONE service group's request-authorization switch and per-version traffic weights.
  - Weight entries must use unique stable service IDs, be non-negative and total exactly 100.
options:
  service_group_id: {type: str, required: true, description: Stable online service-group ID.}
  project_id: {type: str, description: Optional TI workspace ID used to read the group.}
  authorization_enable: {type: bool, description: Whether inference requests require authorization.}
  weights: {type: list, elements: dict, description: WeightEntry-compatible ServiceId and Weight mappings.}
  wait: {type: bool, default: true, description: Wait for weight convergence.}
  waiter_delay: {type: int, default: 5, description: Seconds between state checks.}
  waiter_timeout: {type: int, default: 600, description: Overall weight convergence timeout.}
  retries: {type: int, default: 5, description: Retries for transient API failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tione_model_service_traffic:
    service_group_id: ms-group-xxxxxxxx
    authorization_enable: true
    weights:
      - {ServiceId: ms-v1, Weight: 90}
      - {ServiceId: ms-v2, Weight: 10}
'''
RETURN = r'''
service_group: {description: Effective service-group detail., type: dict, returned: always}
'''

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client
    return models, tione_client


def _model(cls, value): item = cls(); item.from_json_string(json.dumps(value)); return item


def group_request(models, p):
    request = models.DescribeModelServiceGroupRequest(); request.ServiceGroupId = p["service_group_id"]
    if p.get("project_id") is not None: request.TiProjectId = p["project_id"]
    return request


def get(module, client, models, p):
    response = module.sdk_call(client.DescribeModelServiceGroup, group_request(models, p))
    return response.ServiceGroup._serialize(allow_none=True) if response.ServiceGroup else None


def normalized_weights(values):
    return sorted(({"ServiceId": x.get("ServiceId"), "Weight": x.get("Weight")} for x in (values or [])), key=lambda x: x["ServiceId"] or "")


def current_weights(group):
    return normalized_weights({"ServiceId": item.get("ServiceId"), "Weight": item.get("Weight")} for item in ((group or {}).get("Services") or []))


def authorization_request(models, p):
    request = models.ModifyModelServiceAuthorizationRequest(); request.ServiceGroupId = p["service_group_id"]; request.AuthorizationEnable = p["authorization_enable"]
    return request


def weights_request(models, p):
    request = models.ModifyServiceGroupWeightsRequest(); request.ServiceGroupId = p["service_group_id"]
    request.Weights = [_model(models.WeightEntry, item) for item in normalized_weights(p["weights"])]
    return request


def wait_weights(module, client, models, p):
    def poll():
        group = get(module, client, models, p); state = str((group or {}).get("WeightUpdateStatus") or "").lower()
        if state == "update_failed": module.fail_json(msg="TIONE service-group weight update failed", service_group=group)
        if current_weights(group) == normalized_weights(p["weights"]) and state not in ("updating",): return "converged"
        return state
    wait_for_state(module, poll, ["converged"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def validate_weights(module, values):
    if values is None: return
    ids = [item.get("ServiceId") for item in values]; weights = [item.get("Weight") for item in values]
    if not values or any(value in (None, "") for value in ids) or any(value is None for value in weights): module.fail_json(msg="each weight requires ServiceId and Weight")
    if len(ids) != len(set(ids)): module.fail_json(msg="weight ServiceId values must be unique")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in weights): module.fail_json(msg="weights must be non-negative integers")
    if sum(weights) != 100: module.fail_json(msg="weights must total exactly 100", total=sum(weights))


def run_module():
    spec = {
        "service_group_id": {"required": True}, "project_id": {}, "authorization_enable": {"type": "bool"},
        "weights": {"type": "list", "elements": "dict"}, "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5}, "waiter_timeout": {"type": "int", "default": 600},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True); p = module.params
    if p.get("authorization_enable") is None and p.get("weights") is None: module.fail_json(msg="authorization_enable or weights is required")
    validate_weights(module, p.get("weights"))
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        current = get(module, client, models, p)
        if current is None: module.fail_json(msg="TIONE service group does not exist", service_group_id=p["service_group_id"])
        auth_drift = p.get("authorization_enable") is not None and current.get("AuthorizationEnable") != p["authorization_enable"]
        weight_drift = p.get("weights") is not None and current_weights(current) != normalized_weights(p["weights"])
        if not auth_drift and not weight_drift: module.exit_json(changed=False, service_group=current)
        target = dict(current)
        if p.get("authorization_enable") is not None: target["AuthorizationEnable"] = p["authorization_enable"]
        if p.get("weights") is not None:
            target["Services"] = normalized_weights(p["weights"])
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            if auth_drift: module.sdk_call(client.ModifyModelServiceAuthorization, authorization_request(models, p))
            if weight_drift:
                module.sdk_call(client.ModifyServiceGroupWeights, weights_request(models, p))
                if p["wait"]: wait_weights(module, client, models, p)
            current = get(module, client, models, p)
        module.exit_json(changed=True, **(diff_value or {}), service_group=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
